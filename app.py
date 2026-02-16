from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from statistics import median
from typing import Any, List, Optional, Tuple

from flask import Flask, jsonify
import firebase_admin
from firebase_admin import credentials, db

# ================= CONFIG =================
DB_URL = os.getenv(
    "FIREBASE_DB_URL",
    "https://multiplicadores-online-default-rtdb.europe-west1.firebasedatabase.app",
)
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")

app = Flask(__name__)


# ================= FIREBASE =================
def init_firebase() -> None:
    if firebase_admin._apps:
        return

    if not SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "Firebase credentials ausentes. Defina FIREBASE_SERVICE_ACCOUNT_JSON."
        )
    cred_data = json.loads(SERVICE_ACCOUNT_JSON)
    cred = credentials.Certificate(cred_data)

    firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})


# ================= DADOS =================
class Registro:
    def __init__(self, dt: datetime, mult: float, raw: str):
        self.dt = dt
        self.mult = mult
        self.raw = raw


def parse_linha(txt: str, data: str) -> Optional[Registro]:
    if not isinstance(txt, str):
        return None
    m = re.match(r"([0-9.]+)x\s*-\s*(\d{2}:\d{2}:\d{2})", txt)
    if not m:
        return None
    mult, hora = m.groups()
    dt = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M:%S")
    return Registro(dt, float(mult), txt)


def carregar_registros(limite: int = 60) -> List[Registro]:
    ref = db.reference("aviator/historico").get()
    if not isinstance(ref, dict):
        return []

    regs: List[Registro] = []
    for data, itens in ref.items():
        if not isinstance(itens, dict):
            continue
        for v in itens.values():
            r = parse_linha(v, data)
            if r:
                regs.append(r)

    regs.sort(key=lambda x: x.dt)
    return regs[-limite:]


def garantir_hora_futura(dt_prev: datetime, referencia: datetime, passo_segundos: int = 30) -> datetime:
    if passo_segundos <= 0:
        passo_segundos = 30
    if dt_prev > referencia:
        return dt_prev

    atraso = int((referencia - dt_prev).total_seconds())
    saltos = (atraso // passo_segundos) + 1
    return dt_prev + timedelta(seconds=saltos * passo_segundos)


# ================= ANALISE =================
def analisar(registros: List[Registro]) -> dict:
    agora = datetime.now()
    referencia_tempo = agora
    janela_espelho_seg = 150  # 2:30

    if not registros:
        return {
            "decisao": "aguardar",
            "regra": "estatistica_real",
            "motivo_regra": "Sem registros para analise temporal.",
        }

    altos = [r for r in registros if r.mult >= 10]
    if not altos:
        return {
            "decisao": "aguardar",
            "regra": "estatistica_real",
            "motivo_regra": "Sem multiplicador 10+ no recorte.",
        }

    # Alinha a referencia para evitar previsoes no passado em caso de diferenca de fuso/clock.
    referencia_tempo = max(agora, registros[-1].dt)

    ultimo = altos[-1]
    seg_desde_ultimo = int((referencia_tempo - ultimo.dt).total_seconds())

    # ================= REGRA DO ESPELHO (INTERVALO ENTRE OS DOIS ULTIMOS ALTOS) =================
    idx_altos = [i for i, r in enumerate(registros) if r.mult >= 10]
    if len(altos) >= 2:
        penultimo = altos[-2]
        intervalo_espelho = int((ultimo.dt - penultimo.dt).total_seconds())

        # A regra de espelho fica ativa por 2:30 apos o ultimo alto,
        # mesmo com multiplicadores baixos aparecendo no meio.
        if 30 <= intervalo_espelho <= 300 and seg_desde_ultimo < janela_espelho_seg:
            dt_prev = ultimo.dt + timedelta(seconds=max(intervalo_espelho, janela_espelho_seg))
            dt_prev = garantir_hora_futura(dt_prev, referencia_tempo, 30)
            return {
                "decisao": "aguardar",
                "regra": "espelho_intervalo_altos",
                "motivo_regra": "Intervalo de espelho bloqueado por 2:30 apos o ultimo alto.",
                "intervalo_usado_segundos": intervalo_espelho,
                "hora_prevista": dt_prev.strftime("%H:%M:%S"),
            }

    # ================= REGRA 4-5 MINUTOS (deslocada apos 2:30) =================
    dt_4 = ultimo.dt + timedelta(seconds=janela_espelho_seg + 240)
    dt_5 = ultimo.dt + timedelta(seconds=janela_espelho_seg + 300)

    # Antes de chegar no minuto 4+2:30: usa regra de 4 minutos.
    if referencia_tempo < dt_4:
        dt_prev = dt_4
        dt_prev = garantir_hora_futura(dt_prev, referencia_tempo, 30)
        return {
            "decisao": "aguardar",
            "regra": "regra_4_minutos",
            "motivo_regra": "Aguardando 4 minutos apos a janela fixa de 2:30.",
            "hora_prevista": dt_prev.strftime("%H:%M:%S"),
        }

    # Assim que chega/passou do 4+2:30, troca para 5+2:30.
    if referencia_tempo < dt_5:
        dt_prev = dt_5
        dt_prev = garantir_hora_futura(dt_prev, referencia_tempo, 30)
        return {
            "decisao": "aguardar",
            "regra": "regra_5_minutos",
            "motivo_regra": "Janela 4+2:30 atingida; transicao para 5+2:30.",
            "hora_prevista": dt_prev.strftime("%H:%M:%S"),
        }

    # Depois de 5+2:30 sem novo alto, cai para estatistica real.
    return _analise_estatistica_real(registros, referencia_tempo)


def _analise_estatistica_real(registros: List[Registro], referencia_tempo: datetime) -> dict:
    # ================= ESTATISTICA REAL =================
    idx_altos = [i for i, r in enumerate(registros) if r.mult >= 10]
    gaps = [idx_altos[i] - idx_altos[i - 1] for i in range(1, len(idx_altos))]
    gap_medio = median(gaps) if gaps else 8
    gap_atual = (len(registros) - 1) - idx_altos[-1]

    deltas = []
    for i in range(1, len(registros)):
        s = int((registros[i].dt - registros[i - 1].dt).total_seconds())
        if s > 0:
            deltas.append(s)
    intervalo_medio = int(median(deltas)) if deltas else 20

    pressao = gap_atual / max(gap_medio, 1)

    baixos = registros[idx_altos[-1] + 1 :]
    baixos_fracos = len([r for r in baixos if r.mult <= 1.3])
    baixos_medios = len([r for r in baixos if 1.3 < r.mult <= 5])
    total_baixos = max(len(baixos), 1)

    perfil_score = (baixos_fracos * 1.2 + baixos_medios * 0.6) / total_baixos
    score_final = round((pressao * 0.6 + perfil_score * 0.4), 2)

    nivel = "baixo" if score_final < 0.6 else "medio" if score_final < 1.0 else "alto"

    rodadas_faltantes = max(1, int(round(gap_medio - gap_atual)))
    if nivel == "alto":
        fator = 0.6
    elif nivel == "medio":
        fator = 1.0
    else:
        fator = 1.4

    segundos_estimados = max(30, int(rodadas_faltantes * intervalo_medio * fator))
    dt_prev = referencia_tempo + timedelta(seconds=segundos_estimados)
    dt_prev = garantir_hora_futura(dt_prev, referencia_tempo, 30)

    return {
        "decisao": "aguardar",
        "regra": "estatistica_real",
        "motivo_regra": "Nao houve alto nos ultimos 5 minutos; usando modelo estatistico.",
        "nivel_pressao": nivel,
        "score_probabilidade": score_final,
        "gap_atual": gap_atual,
        "gap_medio": gap_medio,
        "hora_prevista": dt_prev.strftime("%H:%M:%S"),
    }


# ================= API =================
@app.get("/health")
def health() -> Tuple[Any, int]:
    return jsonify({"status": "ok"}), 200


@app.get("/bet/10-plus")
def bet_10_plus() -> Tuple[Any, int]:
    init_firebase()
    registros = carregar_registros(60)
    analise = analisar(registros)

    return (
        jsonify(
            {
                "mensagem": "Aguardar",
                "decisao": analise["decisao"],
                "regra": analise["regra"],
                "analise_estatistica": analise,
                "ultimos_60_multiplicadores": [r.raw for r in registros],
            }
        ),
        200,
    )


# ================= MAIN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
