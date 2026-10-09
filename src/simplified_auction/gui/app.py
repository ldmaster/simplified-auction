"""Janela principal (shell) e servicos compartilhados da GUI."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .. import config as config_module
from .. import paths
from ..config import AIConfig
from ..http import HttpClient
from ..providers import resolve_ai_config
from ..store import Store
from .detail import DetailView
from .documents import DocumentsView
from .opportunities import OpportunitiesView
from .pipeline import PipelineView
from .providers import ProvidersView
from .settings import SettingsView


class AuctionApp:
    """Aplicacao Tkinter: notebook de abas + barra de status."""

    def __init__(self, root: tk.Tk, cfg: config_module.Config) -> None:
        """Monta a janela.

        Args:
            root: Janela Tk raiz.
            cfg: Configuracao do app.
        """
        self.root = root
        self.cfg = cfg
        self.store = Store(cfg.db_path)
        self.status = tk.StringVar(value="Pronto.")
        self.progress = tk.StringVar(value="")
        self._queue: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()
        self._busy = False
        self._busy_start = 0.0
        self._busy_label = ""
        self._build()
        self.refresh_counts()
        self.root.after(100, self._poll)

    def _build(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.opportunities = OpportunitiesView(self.notebook, self)
        self.detail = DetailView(self.notebook, self)
        self.pipeline = PipelineView(self.notebook, self)
        self.documents = DocumentsView(self.notebook, self)
        self.settings = SettingsView(self.notebook, self)
        self.providers = ProvidersView(self.notebook, self)

        self.notebook.add(self.opportunities.frame, text="Oportunidades")
        self.notebook.add(self.detail.frame, text="Ficha")
        self.notebook.add(self.pipeline.frame, text="Pipeline")
        self.notebook.add(self.documents.frame, text="Editais")
        self.notebook.add(self.settings.frame, text="Config")
        self.notebook.add(self.providers.frame, text="IA")

        bar = ttk.Frame(self.root)
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status, anchor="w").pack(
            side="left", fill="x", expand=True, padx=4
        )
        ttk.Label(bar, textvariable=self.progress, anchor="e", foreground="#b60").pack(
            side="right", padx=4
        )

    def log_path(self) -> str:
        """Caminho do arquivo de log (para mostrar em caso de erro)."""
        return str(paths.data_dir() / "auction.log")

    def close(self) -> None:
        """Fecha o banco ao encerrar."""
        self.store.close()

    def http(self) -> HttpClient:
        """Cria um cliente HTTP com a configuracao atual."""
        return HttpClient(self.cfg.http)

    def ai_config(self) -> AIConfig:
        """Resolve a configuracao de IA ativa (provedor cadastrado ou ambiente)."""
        return resolve_ai_config()

    def run_async(
        self, work: Callable[[], Any], on_done: Callable[[Any], None], *, label: str = "Trabalhando"
    ) -> None:
        """Executa ``work`` em uma thread e entrega o resultado na thread da UI.

        Args:
            work: Funcao sem argumentos executada em background.
            on_done: Callback chamada na thread principal com o resultado ou
                com a excecao capturada.
            label: Texto do progresso mostrado enquanto roda.
        """
        if self._busy:
            self.status.set("Ja existe uma operacao em andamento; aguarde terminar.")
            return
        self._busy = True
        self._busy_label = label
        self._busy_start = time.monotonic()
        self.status.set(f"{label}...")
        self._update_progress()

        def worker() -> None:
            try:
                result: Any = work()
            except Exception as exc:
                result = exc
            self._queue.put((on_done, result))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self) -> None:
        """Mantem o contador de tempo visivel enquanto ha operacao em background."""
        if not self._busy:
            self.progress.set("")
            return
        elapsed = int(time.monotonic() - self._busy_start)
        self.progress.set(f"aguarde... {elapsed}s")
        self.root.after(250, self._update_progress)

    def _poll(self) -> None:
        """Entrega os resultados das threads na thread principal do Tk."""
        try:
            while True:
                callback, result = self._queue.get_nowait()
                self._busy = False
                self.progress.set("")
                callback(result)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def select_imovel(self, imovel_id: str) -> None:
        """Abre a ficha de um imovel e foca a aba."""
        self.detail.show(imovel_id)
        self.notebook.select(self.detail.frame)

    def refresh_counts(self) -> None:
        """Atualiza as contagens exibidas na aba Config."""
        self.settings.update_counts(self.store.counts())

    def refresh_all(self) -> None:
        """Recarrega todas as abas."""
        self.opportunities.refresh()
        self.pipeline.refresh()
        self.refresh_counts()
