"""Aba "Analise IA": exibe o resultado da IA renderizado (com cores)."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from ..analyze.render import Block, render
from .widgets import style_text, write_blocks

if TYPE_CHECKING:
    from .app import AuctionApp


class AnalysisView:
    """Mostra as analises ja feitas (de um imovel ou de um documento)."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.imovel_id: str | None = None
        self.document_id: int | None = None
        self._rows: list[dict[str, Any]] = []
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        self.choice = tk.StringVar()
        self.combo = ttk.Combobox(
            bar, textvariable=self.choice, state="readonly", width=54
        )
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", lambda _event: self._render_selected())
        ttk.Button(bar, text="Ver JSON", command=self._show_json).pack(side="right")
        ttk.Button(bar, text="Copiar", command=self._copy).pack(side="right", padx=4)
        ttk.Button(bar, text="Atualizar", command=self.refresh).pack(side="right")

        self.text = scrolledtext.ScrolledText(self.frame, wrap="word", padx=10, pady=8)
        self.text.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        style_text(self.text)
        self.text.configure(state="disabled")

    # ------------------------------------------------------------------ dados

    def set_scope(self, *, imovel_id: str | None = None, document_id: int | None = None) -> None:
        """Aponta a visao para um imovel ou um documento e recarrega."""
        self.imovel_id = imovel_id
        self.document_id = document_id
        self.refresh()

    def refresh(self) -> None:
        """Recarrega as analises do escopo atual e exibe a mais recente."""
        empty = "Nenhuma analise ainda."
        if self.imovel_id:
            self._rows = self.app.store.analyses_for(self.imovel_id)
            empty = "Nenhuma analise para este imovel."
        elif self.document_id is not None:
            self._rows = self.app.store.analyses_for_document(self.document_id)
            empty = "Nenhuma analise para este documento."
        else:
            self._rows = []
        labels = [self._label(row, index) for index, row in enumerate(self._rows)]
        self.combo.configure(values=labels)
        if labels:
            self.combo.current(0)
            self._render_row(self._rows[0])
        else:
            self.choice.set("(nenhuma analise ainda)")
            self._render_blocks(
                [
                    Block(empty, "h2"),
                    Block(
                        "Use o botao 'Analisar com IA': escolha os documentos e rode a "
                        "analise (ou gere o prompt para colar em um chat web).",
                        "muted",
                    ),
                ]
            )

    def latest_semaforo(self) -> str:
        """Semaforo da analise mais recente (para o indicador do cabecalho)."""
        if not self._rows:
            return ""
        return str(self._rows[0].get("semaforo") or "").strip().lower()

    @staticmethod
    def _label(row: dict[str, Any], index: int) -> str:
        semaforo = str(row.get("semaforo") or "n/d").upper()
        provider = str(row.get("provider") or "?")
        created = str(row.get("created_at") or "")[:19].replace("T", " ")
        docs = str(row.get("document_ids") or "-")
        prefix = "mais recente — " if index == 0 else ""
        return f"{prefix}{created} | {semaforo} | {provider} | docs {docs}"

    def _render_selected(self) -> None:
        index = self.combo.current()
        if 0 <= index < len(self._rows):
            self._render_row(self._rows[index])

    def _render_row(self, row: dict[str, Any]) -> None:
        try:
            result = json.loads(str(row.get("result_json") or "{}"))
        except json.JSONDecodeError:
            result = {"raw": str(row.get("result_json") or "")}
        meta = (
            f"{row.get('provider') or '?'} · {row.get('model') or 'modelo padrao'} · "
            f"{str(row.get('created_at') or '')[:19].replace('T', ' ')} · "
            f"documentos: {row.get('document_ids') or '-'}"
        )
        self._render_blocks(render(result, meta=meta))

    def _render_blocks(self, blocks: list[Block]) -> None:
        write_blocks(self.text, blocks)

    # ------------------------------------------------------------------ acoes

    def _current_row(self) -> dict[str, Any] | None:
        index = self.combo.current()
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def _show_json(self) -> None:
        row = self._current_row()
        if row is None:
            messagebox.showinfo("Analise", "Nenhuma analise para mostrar.")
            return
        try:
            pretty = json.dumps(
                json.loads(str(row.get("result_json") or "{}")), ensure_ascii=False, indent=2
            )
        except json.JSONDecodeError:
            pretty = str(row.get("result_json") or "")
        window = tk.Toplevel(self.frame)
        window.title("Analise (JSON)")
        window.geometry("760x520")
        view = scrolledtext.ScrolledText(window, wrap="none")
        view.pack(fill="both", expand=True)
        view.insert("1.0", pretty)
        view.configure(state="disabled")

    def _copy(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.app.status.set("Analise copiada para a area de transferencia.")
