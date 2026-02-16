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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT = os.getenv("FIREBASE_SERVICE_ACCOUNT", os.path.join(BASE_DIR, "adminService.json"))
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")

app = Flask(__name__)


# ================= FIREBASE =================
def init_firebase() -> None:
    if firebase_admin._apps:
        return

    if SERVICE_ACCOUNT_JSON:
        cred_data = json.loads(SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(cred_data)
    else:
        cred = credentials.Certificate(SERVICE_ACCOUNT)

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


# ================= ANALISE =================
def analisar(registros: List[Registro]) -> dict:
    agora = datetime.now()

    if not registros:
        return {"decisao": "aguardar", "regra": "estatistica_real"}

    altos = [r for r in registros if r.mult >= 10]
    if not altos:
        return {"decisao": "aguardar", "regra": "estatistica_real"}

    # ================= REGRA DO ESPELHO (INTERVALO ENTRE OS DOIS ULTIMOS ALTOS) =================
    idx_altos = [i for i, r in enumerate(registros) if r.mult >= 10]
    gap_atual = (len(registros) - 1) - idx_altos[-1]

    if len(altos) >= 2 and gap_atual == 0:
        ultimo = altos[-1]
        penultimo = altos[-2]

        intervalo_espelho = int((ultimo.dt - penultimo.dt).total_seconds())

        if 30 <= intervalo_espelho <= 300:
            dt_prev = ultimo.dt + timedelta(seconds=intervalo_espelho)
            if dt_prev <= agora:
                dt_prev = agora + timedelta(seconds=30)

            return {
                "decisao": "aguardar",
                "regra": "espelho_intervalo_altos",
                "intervalo_usado_segundos": intervalo_espelho,
                "hora_prevista": dt_prev.strftime("%H:%M:%S"),
            }

    # ================= ESTATISTICA REAL =================
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
    dt_prev = agora + timedelta(seconds=segundos_estimados)

    return {
        "decisao": "aguardar",
        "regra": "estatistica_real",
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
