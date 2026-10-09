"""Aba Config: contagens, sincronizacao do catalogo e enriquecimento."""

from __future__ import annotations

import contextlib
import shutil
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from .. import paths
from .. import uistate as state
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
        ttk.Label(info, text=f"Log: {self.app.log_path()}").pack(anchor="w", padx=6)
        ai = self.app.ai_config()
        mode = "API" if ai.has_api else "manual (sem chave)"
        ttk.Label(
            info,
            text=f"IA: {ai.provider} ({ai.model or 'modelo padrao'}) — modo {mode} "
            "(configure na aba IA)",
        ).pack(anchor="w", padx=6, pady=(0, 6))

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

        prefs = ttk.LabelFrame(self.frame, text="Preferencias")
        prefs.pack(fill="x", padx=6, pady=6)
        self.auto_analyze = tk.BooleanVar(value=state.auto_analyze())
        ttk.Checkbutton(
            prefs,
            text="Analise de IA automatica (1 clique: gera o prompt, envia e salva)",
            variable=self.auto_analyze,
            command=self._toggle_auto_analyze,
        ).pack(anchor="w", padx=6, pady=6)

        data = ttk.LabelFrame(self.frame, text="Dados")
        data.pack(fill="x", padx=6, pady=6)
        ttk.Label(
            data,
            text="Apaga o que foi coletado (catalogo, fichas, documentos e analises).",
            foreground="#888",
        ).pack(anchor="w", padx=6, pady=(6, 2))
        ttk.Button(
            data, text="Apagar dados sincronizados...", command=self._clear_data
        ).pack(anchor="w", padx=6, pady=(0, 6))

        maps = ttk.LabelFrame(self.frame, text="Google Maps (dentro do app)")
        maps.pack(fill="x", padx=6, pady=6)
        ttk.Label(
            maps,
            text=(
                "Cole a chave da API do Google Maps (Google Cloud > habilitar "
                "'Maps Static API' > billing ativo). A chave fica so no seu computador. "
                "Sem chave, use o mapa interativo (OpenStreetMap), que e gratis."
            ),
            foreground="#888",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(6, 4))
        linha = ttk.Frame(maps)
        linha.pack(fill="x", padx=6, pady=(0, 6))
        self.google_key = tk.StringVar(value=state.google_maps_key())
        ttk.Entry(linha, textvariable=self.google_key, width=54, show="*").pack(side="left")
        ttk.Button(linha, text="Salvar chave", command=self._save_google_key).pack(
            side="left", padx=6
        )
        ttk.Button(linha, text="Limpar", command=self._clear_google_key).pack(side="left")

    def _save_google_key(self) -> None:
        state.set_google_maps_key(self.google_key.get())
        self.app.status.set(
            "Chave do Google Maps salva."
            if self.google_key.get().strip()
            else "Chave do Google Maps removida."
        )

    def _clear_google_key(self) -> None:
        self.google_key.set("")
        state.set_google_maps_key("")
        self.app.status.set("Chave do Google Maps removida.")

    def _toggle_auto_analyze(self) -> None:
        state.set_auto_analyze(self.auto_analyze.get())
        self.app.status.set(
            "Analise automatica ativada." if self.auto_analyze.get()
            else "Analise automatica desativada (abre o dialogo)."
        )

    def _clear_data(self) -> None:
        window = tk.Toplevel(self.frame)
        window.title("Apagar dados sincronizados")
        window.transient(self.app.root)
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Isto apaga os dados coletados. Escolha o que remover:",
            font=("", 11, "bold"),
        ).pack(anchor="w")
        sempre = ttk.Label(
            frame,
            text="• Catalogo, fichas, historico de preco, localizacao e dados externos (sempre)",
        )
        sempre.pack(anchor="w", pady=(6, 2))
        docs = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Documentos baixados (PDFs) e os arquivos do disco", variable=docs
        ).pack(anchor="w")
        analises = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Analises de IA", variable=analises).pack(anchor="w")
        crm = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Pipeline, prazos e due diligence (seus dados de acompanhamento)",
            variable=crm,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Nao da para desfazer.",
            foreground="#b00",
        ).pack(anchor="w", pady=(8, 0))

        def confirmar() -> None:
            if not messagebox.askyesno(
                "Apagar dados",
                "Confirma a remocao dos dados selecionados? Nao da para desfazer.",
                parent=window,
            ):
                return
            counts = self.app.store.clear_synced_data(
                documents=docs.get(), analyses=analises.get(), crm=crm.get()
            )
            if docs.get():
                with contextlib.suppress(OSError):
                    shutil.rmtree(paths.documents_dir(), ignore_errors=True)
            removidos = sum(counts.values())
            window.destroy()
            self.app.status.set(f"Dados apagados: {removidos} registro(s).")
            self.app.opportunities.refresh()
            self.app.pipeline.refresh()
            self.app.documents.refresh()
            self.app.detail.analysis_view.refresh()
            self.app.refresh_counts()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Apagar", command=confirmar).pack(side="left")
        ttk.Button(buttons, text="Cancelar", command=window.destroy).pack(side="left", padx=6)

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

        self.app.run_async(work, self._on_sync, label=f"Sincronizando lista oficial de {uf}")

    def _on_sync(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao sincronizar: {result}")
            messagebox.showerror(
                "Sincronizar", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
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

        self.app.run_async(work, self._on_enrich, label="Enriquecendo fichas")

    def _on_enrich(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao enriquecer: {result}")
            messagebox.showerror(
                "Enriquecer", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
            return
        self.app.status.set(f"{result.fetched}/{result.requested} fichas | falhas {len(result.failed)}")
        self.app.refresh_all()
