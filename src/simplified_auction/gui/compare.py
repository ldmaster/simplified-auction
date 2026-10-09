"""Aba Comparar: compara analises de IA entre imoveis ou entre editais."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from ..analyze.compare import Comparison, compare, comparison_prompt, to_blocks
from ..analyze.render import Block
from .widgets import style_text, write_blocks

if TYPE_CHECKING:
    from .app import AuctionApp

_MAX_SELECAO = 4


class CompareView:
    """Compara duas ou mais analises e mostra o que difere e por que."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.scope = tk.StringVar(value="imoveis")
        self.status = tk.StringVar(value="")
        self._rows: list[dict[str, Any]] = []
        self._comparison: Comparison | None = None
        self._results: list[Any] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Radiobutton(
            bar, text="Analises de imoveis", value="imoveis", variable=self.scope,
            command=self.refresh,
        ).pack(side="left")
        ttk.Radiobutton(
            bar, text="Analises de editais", value="editais", variable=self.scope,
            command=self.refresh,
        ).pack(side="left", padx=(8, 12))
        ttk.Button(bar, text="Comparar", command=self._compare).pack(side="left")
        ttk.Button(bar, text="Explicar com IA", command=self._explain).pack(side="left", padx=4)
        ttk.Button(bar, text="Atualizar", command=self.refresh).pack(side="left")

        ttk.Label(
            self.frame,
            text=(
                "Selecione 2 ou mais analises (Ctrl/Cmd para varias). As linhas em "
                "destaque sao as que diferem."
            ),
            foreground="#888",
        ).pack(anchor="w", padx=6)

        self.listbox = tk.Listbox(self.frame, selectmode="extended", height=6, exportselection=False)
        self.listbox.pack(fill="x", padx=6, pady=(4, 4))

        ttk.Label(self.frame, textvariable=self.status, foreground="#888").pack(
            anchor="w", padx=6
        )

        self.text = scrolledtext.ScrolledText(self.frame, wrap="none", padx=10, pady=8)
        self.text.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        style_text(self.text)
        self.text.configure(state="disabled")

    # ------------------------------------------------------------------ dados

    def refresh(self) -> None:
        """Recarrega a lista de analises do escopo escolhido."""
        self._rows = self.app.store.recent_analyses(imovel=self.scope.get() == "imoveis")
        self.listbox.delete(0, "end")
        for row in self._rows:
            self.listbox.insert("end", self._label(row))
        self.status.set(f"{len(self._rows)} analise(s) disponivel(is).")
        self._comparison = None
        self._results = []

    @staticmethod
    def _label(row: dict[str, Any]) -> str:
        created = str(row.get("created_at") or "")[:19].replace("T", " ")
        semaforo = str(row.get("semaforo") or "n/d").upper()
        if row.get("imovel_id"):
            local = f"{row.get('cidade') or ''}/{row.get('uf') or ''}".strip("/")
            return f"IMOVEL {row['imovel_id']} {local} · {created} · {semaforo}"
        tipo = str(row.get("doc_tipo") or "Documento")[:38]
        return f"{tipo} · {created} · {semaforo}"

    @staticmethod
    def _short_label(row: dict[str, Any]) -> str:
        if row.get("imovel_id"):
            return f"{row['imovel_id']} {str(row.get('cidade') or '')[:18]}"
        return str(row.get("doc_nome") or row.get("doc_tipo") or "Edital")[:28]

    def _selected(self) -> list[dict[str, Any]]:
        return [self._rows[index] for index in self.listbox.curselection()]

    # ------------------------------------------------------------------ acoes

    def _compare(self) -> None:
        selected = self._selected()
        if len(selected) < 2:
            messagebox.showinfo("Comparar", "Selecione 2 ou mais analises (Ctrl/Cmd).")
            return
        if len(selected) > _MAX_SELECAO:
            messagebox.showinfo(
                "Comparar", f"Escolha no maximo {_MAX_SELECAO} analises para caber na tabela."
            )
            return
        labels = [self._short_label(row) for row in selected]
        results: list[Any] = []
        for row in selected:
            try:
                results.append(json.loads(str(row.get("result_json") or "{}")))
            except json.JSONDecodeError:
                results.append({"raw": str(row.get("result_json") or "")})
        self._comparison = compare(labels, results)
        self._results = results
        write_blocks(self.text, to_blocks(self._comparison))
        self.status.set(f"Comparando {len(labels)} analises.")

    def _explain(self) -> None:
        if self._comparison is None:
            messagebox.showinfo("Comparar", "Clique em 'Comparar' primeiro.")
            return
        ai = self.app.ai_config()
        if not ai.has_api:
            messagebox.showinfo(
                "Comparar",
                "A explicacao por IA precisa de um provedor ativo (aba IA). "
                "A comparacao local ja esta na tela.",
            )
            return
        prompt = comparison_prompt(self._comparison, self._results)

        def work() -> Any:
            from ..analyze import run_api

            return run_api(ai, prompt)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self.status.set(f"Falhou a explicacao: {result}")
                messagebox.showerror(
                    "Comparar", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
                )
                return
            blocks = [Block("EXPLICACAO DA IA", "h1"), Block(str(result), "")]
            write_blocks(self.text, blocks)
            self.status.set("Explicacao da IA recebida.")

        self.app.run_async(work, done, label="Comparando com IA")
