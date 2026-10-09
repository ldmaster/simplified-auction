"""Aba Config: contagens, sincronizacao do catalogo e enriquecimento."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..sources.caixa_csv import UFS
from ..sync import enrich, sync_lista

if TYPE_CHECKING:
    from .app import AuctionApp


class SettingsView:
    """Contagens, estado da IA e acoes de coleta em background."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.uf = tk.StringVar(value="AC")
        self.min_desc = tk.StringVar(value="40")
        self._build()
        self.update_counts(self.app.store.counts())

    def _build(self) -> None:
        info = ttk.LabelFrame(self.frame, text="Estado")
        info.pack(fill="x", padx=6, pady=6)
        self.counts = ttk.Label(info, text="")
        self.counts.pack(anchor="w", padx=6, pady=4)
        ttk.Label(info, text=f"Banco: {self.app.cfg.db_path}").pack(anchor="w", padx=6)
        provider = self.app.cfg.ai.provider
        mode = "API" if self.app.cfg.ai.has_api else "manual (sem chave)"
        ttk.Label(info, text=f"IA: provedor {provider} — modo {mode}").pack(anchor="w", padx=6, pady=(0, 6))

        collect = ttk.LabelFrame(self.frame, text="Coleta")
        collect.pack(fill="x", padx=6, pady=6)
        ttk.Label(collect, text="UF").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Combobox(collect, textvariable=self.uf, values=UFS, width=8).grid(row=0, column=1, sticky="w")
        ttk.Button(collect, text="Sincronizar lista oficial", command=self._sync).grid(
            row=0, column=2, padx=6
        )
        ttk.Label(collect, text="Desconto min %").grid(row=1, column=0, sticky="w", padx=6)
        ttk.Entry(collect, textvariable=self.min_desc, width=8).grid(row=1, column=1, sticky="w")
        ttk.Button(collect, text="Enriquecer (limite 50)", command=self._enrich).grid(
            row=1, column=2, padx=6, pady=6
        )

    def update_counts(self, counts: dict[str, int]) -> None:
        """Atualiza o texto de contagens."""
        self.counts.configure(
            text=(
                f"Imoveis: {counts['properties']} (ativos {counts['ativos']}) | "
                f"fichas: {counts['detalhados']} | pipeline: {counts['pipeline']} | "
                f"documentos: {counts['documentos']} | analises: {counts['analises']}"
            )
        )

    def _sync(self) -> None:
        uf = self.uf.get()
        cfg = self.app.cfg
        store = self.app.store

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                return sync_lista(store, client, uf)

        self.app.status.set(f"Sincronizando lista oficial de {uf}...")
        self.app.run_async(work, self._on_sync)

    def _on_sync(self, result: Any) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Sync", str(result))
            return
        up = result.upsert
        self.app.status.set(
            f"{result.uf}: {result.fetched} imoveis | novos {len(up.new)}, "
            f"quedas de preco {len(up.price_drop)}, inativos {len(up.deactivated)}"
        )
        self.app.refresh_all()

    def _enrich(self) -> None:
        uf = self.uf.get() or None
        try:
            min_desc = float(self.min_desc.get()) if self.min_desc.get().strip() else None
        except ValueError:
            min_desc = None
        cfg = self.app.cfg
        store = self.app.store

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                return enrich(store, client, uf=None if uf == "geral" else uf, min_desconto=min_desc, limit=50)

        self.app.status.set("Enriquecendo fichas...")
        self.app.run_async(work, self._on_enrich)

    def _on_enrich(self, result: Any) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Enrich", str(result))
            return
        self.app.status.set(f"{result.fetched}/{result.requested} fichas | falhas {len(result.failed)}")
        self.app.refresh_all()
