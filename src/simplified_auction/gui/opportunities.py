"""Aba Oportunidades: tabela filtravel de imoveis ordenada por score."""

from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any

from .. import uistate as state
from ..scoring import with_score
from ..sources.caixa_csv import UFS

if TYPE_CHECKING:
    from .app import AuctionApp

COLUMNS = (
    ("score", "Score", 60),
    ("desconto", "Desc %", 60),
    ("preco", "Preco", 100),
    ("valor_avaliacao", "Avaliacao", 100),
    ("uf", "UF", 40),
    ("cidade", "Cidade", 140),
    ("bairro", "Bairro", 140),
    ("tipo", "Tipo", 90),
    ("fotos", "Fotos", 55),
    ("modalidade", "Modalidade", 140),
    ("stage", "Estagio", 100),
)


def photo_count(row: dict[str, Any]) -> int:
    """Quantidade de fotos conhecidas de um imovel."""
    fotos = row.get("fotos")
    return len(str(fotos).split("|")) if fotos else 0

EXPORT_FIELDS = [
    "imovel_id", "uf", "cidade", "bairro", "endereco", "tipo", "modalidade",
    "preco", "valor_avaliacao", "desconto", "score", "stage", "link",
]


class OpportunitiesView:
    """Tabela de oportunidades com filtros e exportacao."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.uf = tk.StringVar()
        self.min_desc = tk.StringVar()
        self.text = tk.StringVar()
        self._restore_filters()
        self._build()
        self.refresh()

    def _restore_filters(self) -> None:
        """Restaura os ultimos filtros usados."""
        saved = state.filters("oportunidades")
        self.uf.set(str(saved.get("uf", "")))
        self.min_desc.set(str(saved.get("min_desconto", "")))
        self.text.set(str(saved.get("text", "")))

    def _build(self) -> None:
        filters = ttk.Frame(self.frame)
        filters.pack(fill="x", padx=6, pady=6)
        ttk.Label(filters, text="UF").pack(side="left")
        ttk.Combobox(
            filters, textvariable=self.uf, values=[""] + list(UFS[:-1]), width=5
        ).pack(side="left", padx=(0, 8))
        ttk.Label(filters, text="Desconto min %").pack(side="left")
        ttk.Entry(filters, textvariable=self.min_desc, width=6).pack(side="left", padx=(0, 8))
        ttk.Label(filters, text="Busca").pack(side="left")
        ttk.Entry(filters, textvariable=self.text, width=24).pack(side="left", padx=(0, 8))
        ttk.Button(filters, text="Filtrar", command=self.refresh).pack(side="left")
        ttk.Button(filters, text="Exportar CSV", command=self._export).pack(side="left", padx=4)

        self.tree = ttk.Treeview(
            self.frame, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse"
        )
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.tree.bind("<Double-1>", self._open)

    def _filters(self) -> dict[str, Any]:
        try:
            min_desc = float(self.min_desc.get()) if self.min_desc.get().strip() else None
        except ValueError:
            min_desc = None
        return {
            "uf": self.uf.get().strip() or None,
            "text": self.text.get().strip() or None,
            "min_desconto": min_desc,
        }

    def refresh(self) -> None:
        """Recarrega a tabela com os filtros atuais."""
        state.save_filters(
            "oportunidades",
            {
                "uf": self.uf.get().strip(),
                "min_desconto": self.min_desc.get().strip(),
                "text": self.text.get().strip(),
            },
        )
        rows = with_score(self.app.store.list_properties(**self._filters()))
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "", "end", iid=str(row["imovel_id"]),
                values=(
                    row["score"], f"{float(row['desconto'] or 0):.1f}",
                    f"{float(row['preco'] or 0):,.0f}",
                    f"{float(row['valor_avaliacao'] or 0):,.0f}",
                    row["uf"], row["cidade"], row["bairro"], row["tipo"],
                    photo_count(row) or "",
                    row["modalidade"], row["stage"],
                ),
            )
        self.app.status.set(f"{len(rows)} imoveis listados.")

    def _open(self, _event: Any) -> None:
        selection = self.tree.selection()
        if selection:
            self.app.select_imovel(selection[0])

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if not path:
            return
        rows = with_score(self.app.store.list_properties(**self._filters()))
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        self.app.status.set(f"{len(rows)} imoveis exportados para {path}")
