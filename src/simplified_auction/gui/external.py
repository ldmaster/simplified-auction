"""Sub-aba "Dados externos": CEP e CNPJ de fontes publicas gratuitas."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..analyze.extract import extract_text
from ..config import external_http_config
from ..sources.external import (
    describe_cep,
    describe_cnpj,
    extract_cnpjs,
    lookup_cep,
    lookup_cnpj,
)

if TYPE_CHECKING:
    from .app import AuctionApp


def _external_client(cfg: Any) -> Any:
    """Cliente HTTP para APIs abertas (sem fingerprint de navegador)."""
    from ..http import HttpClient

    return HttpClient(external_http_config(cfg.http))


class ExternalView:
    """Consulta e exibe dados externos do imovel (CEP e CNPJs da matricula)."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.imovel_id: str | None = None
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(bar, text="Buscar endereco (CEP)", command=self._fetch_cep).pack(side="left")
        ttk.Button(bar, text="Buscar CNPJs da matricula", command=self._fetch_cnpj).pack(
            side="left", padx=4
        )
        ttk.Button(bar, text="Limpar", command=self._clear).pack(side="left")
        self.status = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status, foreground="#888").pack(side="right")

        self.tree = ttk.Treeview(
            self.frame, columns=("campo", "valor"), show="tree headings", height=14
        )
        self.tree.heading("#0", text="Fonte")
        self.tree.heading("campo", text="Campo")
        self.tree.heading("valor", text="Valor")
        self.tree.column("#0", width=170)
        self.tree.column("campo", width=190)
        self.tree.column("valor", width=430)
        self.tree.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        ttk.Label(
            self.frame,
            text=(
                "Fontes publicas gratuitas: CEP (BrasilAPI/ViaCEP) e CNPJ (BrasilAPI). "
                "Onus reais, preco de mercado, IPTU e areas de risco exigem chave, "
                "captcha ou pagamento e nao sao consultados aqui."
            ),
            foreground="#888",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=4, pady=(0, 4))

    # ------------------------------------------------------------------ dados

    def set_imovel(self, imovel_id: str | None) -> None:
        """Aponta a visao para um imovel e recarrega os dados salvos."""
        self.imovel_id = imovel_id
        self._render()

    def _render(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.imovel_id:
            self.status.set("")
            return
        data = self.app.store.get_enrichment(self.imovel_id)
        cep = data.get("cep")
        if cep:
            node = self.tree.insert("", "end", text="Endereco (CEP)", open=True)
            for label, value in describe_cep(cep):
                self.tree.insert(node, "end", values=(label, value))
        itens = (data.get("cnpj") or {}).get("itens") or {}
        for digits, info in itens.items():
            node = self.tree.insert("", "end", text=f"CNPJ {digits}", open=True)
            for label, value in describe_cnpj(info):
                self.tree.insert(node, "end", values=(label, value))
        total = (1 if cep else 0) + len(itens)
        self.status.set(f"{total} fonte(s) consultada(s)" if total else "sem dados externos")

    # ------------------------------------------------------------------ acoes

    def _fetch_cep(self) -> None:
        if not self.imovel_id:
            return
        detail = self.app.store.get_detail(self.imovel_id) or {}
        cep = str(detail.get("cep") or "")
        if not cep:
            messagebox.showinfo(
                "Dados externos",
                "Sem CEP: enriqueça a ficha do imovel primeiro (botao 'Enriquecer ficha').",
            )
            return
        imovel_id = self.imovel_id
        cfg = self.app.cfg
        store = self.app.store

        def work() -> Any:
            with _external_client(cfg) as client:
                return lookup_cep(client, cep)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self._fail(result)
                return
            if not result:
                self.status.set("CEP nao encontrado nas fontes publicas.")
                return
            store.save_enrichment(imovel_id, "cep", json.dumps(result, ensure_ascii=False))
            self._render()

        self.app.run_async(work, done, label=f"Consultando CEP {cep}")

    def _fetch_cnpj(self) -> None:
        if not self.imovel_id:
            return
        imovel_id = self.imovel_id
        cfg = self.app.cfg
        store = self.app.store
        docs = [
            doc
            for doc in store.list_documents(imovel_id=imovel_id)
            if doc.get("local_path")
        ]
        matricula = next(
            (doc for doc in docs if str(doc.get("tipo") or "").lower().startswith("matric")),
            None,
        )
        if matricula is None:
            messagebox.showinfo(
                "Dados externos",
                "Baixe a matricula (botao na Ficha) para procurar CNPJs no documento.",
            )
            return
        caminho = str(matricula["local_path"])

        def work() -> Any:
            text = extract_text(Path(caminho))
            found = extract_cnpjs(text)[:3]
            if not found:
                return {}
            itens: dict[str, Any] = {}
            with _external_client(cfg) as client:
                for digits in found:
                    info = lookup_cnpj(client, digits)
                    if info:
                        itens[digits] = info
            return itens

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self._fail(result)
                return
            if not result:
                self.status.set("Nenhum CNPJ encontrado na matricula.")
                return
            store.save_enrichment(
                imovel_id, "cnpj", json.dumps({"itens": result}, ensure_ascii=False)
            )
            self._render()

        self.app.run_async(work, done, label="Consultando CNPJs da matricula")

    def _clear(self) -> None:
        if not self.imovel_id:
            return
        self.app.store.clear_enrichment(self.imovel_id)
        self._render()

    def _fail(self, error: Exception) -> None:
        self.app.status.set(f"Falhou a consulta externa: {error}")
        messagebox.showerror(
            "Dados externos", f"{error}\n\nDetalhes no log:\n{self.app.log_path()}"
        )
