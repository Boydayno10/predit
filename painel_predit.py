import copy
import json
import threading
import tkinter as tk
from tkinter import ttk
import urllib.error
import urllib.request

DEFAULT_API = "https://server-preditor.onrender.com/bet/10-plus"


class PainelPredit:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Predit Premium")
        self.root.geometry("860x620")
        self.root.minsize(760, 560)

        self.url_var = tk.StringVar(value=DEFAULT_API)
        self.show_multipliers_var = tk.BooleanVar(value=False)
        self.auto_update_var = tk.BooleanVar(value=True)
        self.interval_var = tk.StringVar(value="10")
        self.status_var = tk.StringVar(value="Pronto")
        self.hora_var = tk.StringVar(value="--:--:--")
        self.regra_var = tk.StringVar(value="-")
        self._fetching = False

        self._setup_style()
        self._build_ui()

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#10131a")

        style.configure("Main.TFrame", background="#10131a")
        style.configure("Panel.TFrame", background="#161b25")
        style.configure("Title.TLabel", background="#10131a", foreground="#f5f7ff", font=("Segoe UI", 17, "bold"))
        style.configure("Subtitle.TLabel", background="#10131a", foreground="#a8b2c7", font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background="#161b25", foreground="#d7deef", font=("Segoe UI", 10, "bold"))
        style.configure("ValueTime.TLabel", background="#161b25", foreground="#8ff0c6", font=("Consolas", 30, "bold"))
        style.configure("ValueRule.TLabel", background="#161b25", foreground="#f5f7ff", font=("Segoe UI", 15, "bold"))
        style.configure("TLabel", background="#10131a", foreground="#d7deef")
        style.configure("TCheckbutton", background="#10131a", foreground="#d7deef")
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
        auto_bar.pack(fill="x", pady=(0, 8))
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
            values=("5", "10", "15", "20", "30", "60"),
            width=5,
            state="readonly",
        )
        self.interval_combo.pack(side="left")

        cards = ttk.Frame(main, style="Main.TFrame")
        cards.pack(fill="x", pady=(2, 12))

        card_hora = ttk.Frame(cards, style="Panel.TFrame", padding=12)
        card_hora.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(card_hora, text="Hora Prevista", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(card_hora, textvariable=self.hora_var, style="ValueTime.TLabel").pack(anchor="w", pady=(4, 0))

        card_regra = ttk.Frame(cards, style="Panel.TFrame", padding=12)
        card_regra.pack(side="left", fill="x", expand=True)
        ttk.Label(card_regra, text="Regra Ativa", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(card_regra, textvariable=self.regra_var, style="ValueRule.TLabel").pack(anchor="w", pady=(12, 0))

        self.chk = ttk.Checkbutton(
            main,
            text="Mostrar multiplicadores",
            variable=self.show_multipliers_var,
            command=self._toggle_multipliers,
        )
        self.chk.pack(anchor="w", pady=(0, 8))

        self.mult_frame = ttk.Frame(main, style="Panel.TFrame", padding=10)
        ttk.Label(self.mult_frame, text="Multiplicadores", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 6))
        self.mult_text = tk.Text(
            self.mult_frame,
            height=10,
            wrap="word",
            bg="#0f1420",
            fg="#dbe5ff",
            insertbackground="#dbe5ff",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.mult_text.pack(fill="both", expand=True)
        self.mult_text.config(state="disabled")

        result_frame = ttk.Frame(main, style="Panel.TFrame", padding=10)
        result_frame.pack(fill="both", expand=True)
        ttk.Label(result_frame, text="Resultado", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 6))
        self.result_text = tk.Text(
            result_frame,
            wrap="word",
            bg="#0f1420",
            fg="#dbe5ff",
            insertbackground="#dbe5ff",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.result_text.pack(fill="both", expand=True)
        self.result_text.config(state="disabled")

        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

        self._toggle_multipliers()
        self._schedule_auto(initial=True)

    def _toggle_multipliers(self) -> None:
        if self.show_multipliers_var.get():
            self.mult_frame.pack(fill="both", expand=False, pady=(0, 8))
        else:
            self.mult_frame.pack_forget()
            self._set_text(self.mult_text, "")

    @staticmethod
    def _format_regra(regra: str) -> str:
        if not regra:
            return "-"
        txt = regra.replace("_", " ").replace("-", " ").strip()
        return " ".join(p.capitalize() for p in txt.split())

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
            self.root.after(0, self._render_error, f"HTTP {e.code}\n{body}")
        except Exception as e:
            self.root.after(0, self._render_error, str(e))

    def _render_success(self, data: dict) -> None:
        analise = data.get("analise_estatistica", {}) if isinstance(data, dict) else {}
        hora = analise.get("hora_prevista") or data.get("hora_prevista") or "--:--:--"
        regra = data.get("regra") or analise.get("regra") or data.get("regra_previsao") or "-"

        self.hora_var.set(str(hora))
        self.regra_var.set(self._format_regra(str(regra)))

        view_data = copy.deepcopy(data)
        mults = []
        if isinstance(view_data, dict):
            mults = view_data.pop("ultimos_60_multiplicadores", [])

        if self.show_multipliers_var.get() and isinstance(mults, list):
            self._set_text(self.mult_text, "\n".join(mults))
        else:
            self._set_text(self.mult_text, "")

        self._set_text(self.result_text, json.dumps(view_data, indent=2, ensure_ascii=False))

        self.status_var.set("Consulta concluida")
        self.btn_predict.config(state="normal")
        self._fetching = False
        self._schedule_auto()

    def _render_error(self, msg: str) -> None:
        self._set_text(self.result_text, msg)
        self.status_var.set("Erro na consulta")
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
            interval = 10
        delay_ms = 300 if initial else interval * 1000
        self.root.after(delay_ms, self.on_predict)

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    PainelPredit(root)
    root.mainloop()


if __name__ == "__main__":
    main()
