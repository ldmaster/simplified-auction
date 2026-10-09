"""Janela principal (shell) e servicos compartilhados da GUI."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .. import config as config_module
from ..http import HttpClient
from ..store import Store
from .detail import DetailView
from .documents import DocumentsView
from .opportunities import OpportunitiesView
from .pipeline import PipelineView
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
        self._build()
        self.refresh_counts()

    def _build(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.opportunities = OpportunitiesView(self.notebook, self)
        self.detail = DetailView(self.notebook, self)
        self.pipeline = PipelineView(self.notebook, self)
        self.documents = DocumentsView(self.notebook, self)
        self.settings = SettingsView(self.notebook, self)

        self.notebook.add(self.opportunities.frame, text="Oportunidades")
        self.notebook.add(self.detail.frame, text="Ficha")
        self.notebook.add(self.pipeline.frame, text="Pipeline")
        self.notebook.add(self.documents.frame, text="Editais")
        self.notebook.add(self.settings.frame, text="Config")

        bar = ttk.Label(self.root, textvariable=self.status, anchor="w", relief="sunken")
        bar.pack(fill="x", side="bottom")

    def close(self) -> None:
        """Fecha o banco ao encerrar."""
        self.store.close()

    def http(self) -> HttpClient:
        """Cria um cliente HTTP com a configuracao atual."""
        return HttpClient(self.cfg.http)

    def run_async(self, work: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        """Executa ``work`` em uma thread e entrega o resultado na thread da UI.

        Args:
            work: Funcao sem argumentos executada em background.
            on_done: Callback chamada na thread principal com o resultado ou
                com a excecao capturada.
        """

        def worker() -> None:
            try:
                result: Any = work()
            except Exception as exc:
                result = exc
            self.root.after(0, lambda: on_done(result))

        threading.Thread(target=worker, daemon=True).start()

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
