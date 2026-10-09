"""Aba Editais: publicacoes legais da Caixa (listar, baixar e analisar PDFs)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..models import DOCUMENT_TYPES
from ..sources import caixa_docs
from ..sources.caixa_csv import UFS
from .analysis import AnalysisView
from .analyze_dialog import open_analyze_dialog

if TYPE_CHECKING:
    from .app import AuctionApp

COLUMNS = (
    ("uf", "UF", 40),
    ("ano", "Ano", 50),
    ("mes", "Mes", 50),
    ("tipo", "Tipo", 280),
    ("nome", "Arquivo", 200),
    ("baixado", "Baixado", 70),
)


class DocumentsView:
    """Lista, baixa e analisa com IA os editais/avisos publicados."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.uf = tk.StringVar(value="AC")
        self.ano = tk.StringVar(value="2026")
        self.mes = tk.StringVar(value="10")
        self.tipo = tk.StringVar(value="9")
        self._build()
        self.refresh()

    def _build(self) -> None:
        notebook = ttk.Notebook(self.frame)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook

        listing = ttk.Frame(notebook)
        notebook.add(listing, text="Publicacoes")
        self._build_listing(listing)

        self.analysis_view = AnalysisView(notebook, self.app)
        notebook.add(self.analysis_view.frame, text="Analise IA")

    def _build_listing(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="UF").pack(side="left")
        ttk.Combobox(top, textvariable=self.uf, values=list(UFS[:-1]), width=5).pack(
            side="left", padx=(0, 6)
        )
        ttk.Label(top, text="Ano").pack(side="left")
        ttk.Entry(top, textvariable=self.ano, width=6).pack(side="left", padx=(0, 6))
        ttk.Label(top, text="Mes").pack(side="left")
        ttk.Entry(top, textvariable=self.mes, width=4).pack(side="left", padx=(0, 6))
        ttk.Label(top, text="Tipo").pack(side="left")
        ttk.Combobox(
            top, textvariable=self.tipo, width=6, values=sorted(DOCUMENT_TYPES),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Consultar site", command=self._list).pack(side="left")
        ttk.Button(top, text="Baixar PDFs", command=self._fetch).pack(side="left", padx=4)
        ttk.Button(top, text="Analisar com IA", command=self._analyze_selected).pack(
            side="left", padx=4
        )

        ttk.Label(
            parent,
            text=(
                "Selecione um documento com PDF baixado e clique em 'Analisar com IA' "
                "(ou visualize uma analise ja feita na sub-aba 'Analise IA')."
            ),
            foreground="#666",
        ).pack(anchor="w", padx=6)

        self.tree = ttk.Treeview(parent, columns=[c[0] for c in COLUMNS], show="headings")
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._on_select())

    def refresh(self) -> None:
        """Recarrega a lista local de documentos."""
        rows = self.app.store.list_documents(limit=500)
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "", "end", iid=str(row["id"]),
                values=(
                    row["uf"], row["ano"], row["mes"], row["tipo"], row["nome"],
                    "sim" if row.get("local_path") else "nao",
                ),
            )
        self.app.status.set(f"{len(rows)} documento(s) no banco.")

    # ------------------------------------------------------------------ acoes

    def _selected_document(self) -> dict[str, Any] | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.app.store.get_document(int(selection[0]))

    def _on_select(self) -> None:
        document = self._selected_document()
        if document is not None:
            self.analysis_view.set_scope(document_id=int(document["id"]))

    def _analyze_selected(self) -> None:
        document = self._selected_document()
        if document is None:
            messagebox.showinfo("Editais", "Selecione um documento na lista.")
            return
        if not document.get("local_path"):
            messagebox.showinfo(
                "Editais",
                "Baixe o PDF primeiro (botao 'Baixar PDFs') para poder analisar.",
            )
            return
        doc_id = int(document["id"])
        self.analysis_view.set_scope(document_id=doc_id)
        open_analyze_dialog(
            self.app,
            preselect=[doc_id],
            on_saved=lambda: self._on_analysis_saved(doc_id),
        )

    def _on_analysis_saved(self, doc_id: int) -> None:
        self.analysis_view.set_scope(document_id=doc_id)
        self.notebook.select(self.analysis_view.frame)

    def _params(self) -> tuple[str, int, int, str]:
        return self.uf.get(), int(self.ano.get() or 0), int(self.mes.get() or 0), self.tipo.get()

    def _use_browser(self) -> bool:
        return bool(self.app.cfg.http.browser)

    def _list(self) -> None:
        uf, ano, mes, tipo = self._params()
        cfg = self.app.cfg
        store = self.app.store
        use_browser = self._use_browser()

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                if not use_browser:
                    caixa_docs.bootstrap(client)
                docs = caixa_docs.list_documents(
                    client, uf=uf, mes=mes, ano=ano, tipo=tipo, browser=use_browser
                )
            for doc in docs:
                store.upsert_document(doc)
            return len(docs)

        self.app.run_async(
            work, self._on_listed, label=f"Consultando editais de {uf} {mes:02d}/{ano}"
        )

    def _on_listed(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao consultar editais: {result}")
            messagebox.showerror(
                "Editais", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
            return
        self.app.status.set(f"{result} documento(s) encontrados.")
        self.refresh()
        self.app.refresh_counts()

    def _fetch(self) -> None:
        uf, ano, mes, tipo = self._params()
        cfg = self.app.cfg
        store = self.app.store
        use_browser = self._use_browser()

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                if not use_browser:
                    caixa_docs.bootstrap(client)
                docs = caixa_docs.list_documents(
                    client, uf=uf, mes=mes, ano=ano, tipo=tipo, browser=use_browser
                )
                count = 0
                for doc in docs:
                    doc_id = store.upsert_document(doc)
                    caixa_docs.download(client, store, doc_id, ajax=False)
                    count += 1
            return count

        self.app.run_async(work, self._on_fetched, label=f"Baixando {tipo} {mes:02d}/{ano}")

    def _on_fetched(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao baixar editais: {result}")
            messagebox.showerror(
                "Editais", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
            return
        self.app.status.set(f"{result} PDF(s) baixados.")
        self.refresh()
        self.app.refresh_counts()
