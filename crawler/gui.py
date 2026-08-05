"""Interface gráfica simples (tkinter) para geração de editais.

Pensada para usuários sem conhecimento técnico: duplo clique no
executável -> janela com um botão -> planilha gerada ao lado.
"""

import asyncio
import logging
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)


def _default_output_dir() -> Path:
    """Pasta onde os arquivos serão gerados: ao lado do exe (PyInstaller)
    ou no diretório de trabalho atual."""
    if getattr(sys, "frozen", False):  # rodando como exe (PyInstaller)
        return Path(sys.executable).parent
    return Path.cwd()


class EditaisApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Gerador de Editais — PRPGI")
        root.geometry("720x560")
        root.minsize(600, 480)

        self.output_dir = tk.StringVar(value=str(_default_output_dir()))
        self.log_queue: queue.Queue = queue.Queue()
        self._running = False

        self._build_ui()
        self._poll_log()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Gerador de Editais de Fomento à Pesquisa",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", **pad)

        ttk.Label(
            main,
            text=(
                "Coleta editais de CAPES, CNPq, FINEP, FAPESB e SETEC "
                "e gera a planilha editais.xlsx ao lado deste programa."
            ),
            wraplength=660,
        ).pack(anchor="w", padx=12)

        # Pasta de saída
        row = ttk.Frame(main)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Pasta de saída:").pack(side="left")
        ttk.Entry(row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Escolher…", command=self._choose_dir).pack(side="right")

        # Botão principal
        self.btn = ttk.Button(
            main,
            text="Gerar Editais",
            command=self._start,
            style="Accent.TButton",
        )
        self.btn.pack(fill="x", **pad)

        # Barra de progresso (indeterminada)
        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x", padx=12)

        # Log
        ttk.Label(main, text="Progresso:").pack(anchor="w", padx=12)
        self.log_box = scrolledtext.ScrolledText(main, height=14, state="disabled", font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir.get())
        if chosen:
            self.output_dir.set(chosen)

    def _log(self, msg: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _poll_log(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._log(msg)
        except queue.Empty:
            pass
        if self._running:
            self.progress.start(12)
        else:
            self.progress.stop()
        self.root.after(150, self._poll_log)

    def _start(self) -> None:
        if self._running:
            return
        out_dir = Path(self.output_dir.get()).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Erro", f"Não foi possível criar a pasta:\n{out_dir}\n\n{e}")
            return

        self._running = True
        self.btn.configure(state="disabled", text="Gerando…")
        self.log_queue.put(f"Pasta de saída: {out_dir}")
        self.log_queue.put("Iniciando coleta…")

        thread = threading.Thread(target=self._run_crawler, args=(out_dir,), daemon=True)
        thread.start()

    def _run_crawler(self, out_dir: Path) -> None:
        try:
            from crawler.config import Settings
            from crawler.main import run_crawler

            class _QHandler(logging.Handler):
                def emit(self, record):  # pragma: no cover - simples
                    self.queue.put(self.format(record))

            handler = _QHandler()
            handler.queue = self.log_queue
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(handler)

            settings = Settings(
                db_path=str(out_dir / "oportunidades.db"),
                csv_path=str(out_dir / "editais.csv"),
                xlsx_path=str(out_dir / "editais.xlsx"),
                html_path=str(out_dir / "editais.html"),
            )
            asyncio.run(run_crawler(selected_parser="all", settings=settings))

            root_logger.removeHandler(handler)
            self.log_queue.put("")
            self.log_queue.put("✅ Concluído! Arquivos gerados em:")
            self.log_queue.put(f"   {out_dir}")
            self.log_queue.put("   Abra o arquivo editais.xlsx no Excel.")
        except Exception as e:  # pragma: no cover
            self.log_queue.put(f"ERRO: {e}")
        finally:
            self.root.after(0, self._finish)

    def _finish(self) -> None:
        self._running = False
        self.btn.configure(state="normal", text="Gerar Editais")
        messagebox.showinfo(
            "Concluído",
            f"Planilha gerada em:\n{self.output_dir.get()}\n\nAbra o arquivo editais.xlsx no Excel.",
        )


def main() -> None:
    logging.basicConfig(level=logging.WARNING)  # mantém terminal limpo; UI usa handler
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        style.theme_use("vista")
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"))
    except tk.TclError:
        pass
    EditaisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
