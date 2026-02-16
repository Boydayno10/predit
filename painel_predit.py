import json
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
import urllib.error
import urllib.request

DEFAULT_API = "https://server-preditor.onrender.com/bet/10-plus"


class PainelPredit:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Predit Premium")
        self.root.geometry("800x340")
        self.root.minsize(760, 320)

        self.url_var = tk.StringVar(value=DEFAULT_API)
        self.auto_update_var = tk.BooleanVar(value=True)
        self.interval_var = tk.StringVar(value="5")
        self.status_var = tk.StringVar(value="Pronto")
        self.hora_var = tk.StringVar(value="--:--:--")
        self.regra_var = tk.StringVar(value="-")
        self.detalhe_var = tk.StringVar(value="")

        self._fetching = False

        self._setup_style()
        self._build_ui()

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#0d1320")

        style.configure("Main.TFrame", background="#0d1320")
        style.configure("Panel.TFrame", background="#141e2f")
        style.configure("Title.TLabel", background="#0d1320", foreground="#f5f7ff", font=("Segoe UI", 17, "bold"))
        style.configure("Subtitle.TLabel", background="#0d1320", foreground="#a8b2c7", font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background="#141e2f", foreground="#d7deef", font=("Segoe UI", 10, "bold"))
        style.configure("ValueTime.TLabel", background="#141e2f", foreground="#8ff0c6", font=("Consolas", 37, "bold"))
        style.configure("ValueRule.TLabel", background="#141e2f", foreground="#f5f7ff", font=("Segoe UI", 15, "bold"))
        style.configure("Detail.TLabel", background="#141e2f", foreground="#9db0cf", font=("Segoe UI", 9))
        style.configure("TLabel", background="#0d1320", foreground="#d7deef")
        style.configure("TCheckbutton", background="#0d1320", foreground="#d7deef")
        style.configure("TEntry", fieldbackground="#0f1420", foreground="#eef2ff")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, style="Main.TFrame", padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Predit", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Previsao de 10+ em tempo real", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))

        top = ttk.Frame(main, style="Main.TFrame")
        top.pack(fill="x", pady=(0, 10))

        ttk.Label(top, text="API:").pack(side="left")
        ttk.Entry(top, textvariable=self.url_var).pack(side="left", fill="x", expand=True, padx=8)
        self.btn_predict = ttk.Button(top, text="Predit", style="Primary.TButton", command=self.on_predict)
        self.btn_predict.pack(side="left")

        auto_bar = ttk.Frame(main, style="Main.TFrame")
        auto_bar.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            auto_bar,
            text="Atualizacao automatica",
            variable=self.auto_update_var,
            command=self._on_toggle_auto,
        ).pack(side="left")
        ttk.Label(auto_bar, text="Intervalo (s):").pack(side="left", padx=(12, 6))
        self.interval_combo = ttk.Combobox(
            auto_bar,
            textvariable=self.interval_var,
            values=("3", "5", "10", "15", "20", "30", "60"),
            width=5,
            state="readonly",
        )
        self.interval_combo.pack(side="left")

        cards = ttk.Frame(main, style="Main.TFrame")
        cards.pack(fill="x", pady=(2, 6))

        card_hora = ttk.Frame(cards, style="Panel.TFrame", padding=12)
        card_hora.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(card_hora, text="Hora Prevista", style="PanelTitle.TLabel").pack(anchor="w")

        row = ttk.Frame(card_hora, style="Panel.TFrame")
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, textvariable=self.hora_var, style="ValueTime.TLabel").pack(side="left", anchor="w")
        ttk.Label(row, textvariable=self.detalhe_var, style="Detail.TLabel", justify="left").pack(side="left", anchor="s", padx=(16, 0), pady=(12, 0))

        card_regra = ttk.Frame(cards, style="Panel.TFrame", padding=12)
        card_regra.pack(side="left", fill="x", expand=True)
        ttk.Label(card_regra, text="Regra Ativa", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(card_regra, textvariable=self.regra_var, style="ValueRule.TLabel").pack(anchor="w", pady=(18, 0))

        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

        self._schedule_auto(initial=True)

    @staticmethod
    def _format_regra(regra: str) -> str:
        if not regra:
            return "-"
        txt = regra.replace("_", " ").replace("-", " ").strip()
        return " ".join(p.capitalize() for p in txt.split())

    @staticmethod
    def _parse_mult_line(line: str) -> tuple[float, datetime] | None:
        try:
            left, right = line.split(" - ")
            mtxt = left.replace("x", "").strip()
            mult = float(mtxt)
            hora = datetime.strptime(right.strip(), "%H:%M:%S")
            return mult, hora
        except Exception:
            return None

    def _build_detalhe(self, data: dict, analise: dict, regra_raw: str) -> str:
        mults = data.get("ultimos_60_multiplicadores", []) if isinstance(data, dict) else []
        parsed = [self._parse_mult_line(x) for x in mults if isinstance(x, str)]
        parsed = [p for p in parsed if p is not None]
        altos = [p for p in parsed if p[0] >= 10.0]

        regra_norm = (regra_raw or "").lower()

        if ("espelho" in regra_norm) and len(altos) >= 2:
            m1, t1 = altos[-2]
            m2, t2 = altos[-1]
            diff = int((t2 - t1).total_seconds())
            if diff < 0:
                diff += 24 * 3600
            inter = analise.get("intervalo_usado_segundos")
            intervalo = int(inter) if isinstance(inter, (int, float)) else diff
            return f"{m1:.2f}x | {m2:.2f}x\nintervalo: {intervalo}s"

        if regra_norm in {"regra_4_minutos", "regra_5_minutos"} and len(altos) >= 1:
            m, _ = altos[-1]
            plus = "+4m" if regra_norm == "regra_4_minutos" else "+5m"
            return f"base: {m:.2f}x {plus}"

        return ""

    def on_predict(self) -> None:
        if self._fetching:
            return
        self.btn_predict.config(state="disabled")
        self.status_var.set("Consultando API...")
        self._fetching = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        url = self.url_var.get().strip()
        req = urllib.request.Request(url=url, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                self.root.after(0, self._render_success, data)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self.root.after(0, self._render_error, f"HTTP {e.code}: {body}")
        except Exception as e:
            self.root.after(0, self._render_error, str(e))

    def _render_success(self, data: dict) -> None:
        analise = data.get("analise_estatistica", {}) if isinstance(data, dict) else {}
        hora = analise.get("hora_prevista") or data.get("hora_prevista") or "--:--:--"
        regra_raw = data.get("regra") or analise.get("regra") or data.get("regra_previsao") or "-"

        self.hora_var.set(str(hora))
        self.regra_var.set(self._format_regra(str(regra_raw)))
        self.detalhe_var.set(self._build_detalhe(data, analise, str(regra_raw)))

        self.status_var.set("Atualizado")
        self.btn_predict.config(state="normal")
        self._fetching = False
        self._schedule_auto()

    def _render_error(self, msg: str) -> None:
        self.status_var.set(f"Erro: {msg}")
        self.btn_predict.config(state="normal")
        self._fetching = False
        self._schedule_auto()

    def _on_toggle_auto(self) -> None:
        if self.auto_update_var.get():
            self.status_var.set("Auto ligado")
            self._schedule_auto(initial=True)
        else:
            self.status_var.set("Auto desligado")

    def _schedule_auto(self, initial: bool = False) -> None:
        if not self.auto_update_var.get() or self._fetching:
            return
        try:
            interval = max(2, int(self.interval_var.get()))
        except ValueError:
            interval = 5
        delay_ms = 300 if initial else interval * 1000
        self.root.after(delay_ms, self.on_predict)


def main() -> None:
    root = tk.Tk()
    PainelPredit(root)
    root.mainloop()


if __name__ == "__main__":
    main()
