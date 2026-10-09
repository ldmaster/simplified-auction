"""Aba Pipeline: imoveis em andamento por estagio."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

from ..models import STAGE_LABELS, STAGES

if TYPE_CHECKING:
    from .app import AuctionApp

COLUMNS = (
    ("imovel_id", "Imovel", 130),
    ("stage", "Estagio", 110),
    ("cidade", "Cidade", 150),
    ("tipo", "Tipo", 90),
    ("desconto", "Desc %", 60),
    ("decisao", "Decisao", 90),
)


class PipelineView:
    """Visao do pipeline (estagios, decisao e atalho para a ficha)."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.stage_var = tk.StringVar(value=STAGE_LABELS["triagem"])
        self._build()
        self.refresh()

    def _build(self) -> None:
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Mover selecionado para").pack(side="left")
        ttk.Combobox(
            top, textvariable=self.stage_var, width=16,
            values=[STAGE_LABELS[s] for s in STAGES], state="readonly",
        ).pack(side="left", padx=4)
        ttk.Button(top, text="Aplicar", command=self._move).pack(side="left")
        ttk.Button(top, text="Atualizar", command=self.refresh).pack(side="left", padx=4)
        self.summary = ttk.Label(top, text="")
        self.summary.pack(side="right")

        self.tree = ttk.Treeview(
            self.frame, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse"
        )
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.tree.bind("<Double-1>", self._open)

    def refresh(self) -> None:
        """Recarrega a visao do pipeline."""
        rows = self.app.store.list_pipeline()
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "", "end", iid=str(row["imovel_id"]),
                values=(
                    row["imovel_id"], STAGE_LABELS.get(str(row["stage"]), row["stage"]),
                    row["cidade"], row["tipo"], f"{float(row['desconto'] or 0):.1f}",
                    row["decisao"],
                ),
            )
        counts = self.app.store.stage_counts()
        summary = "  ".join(
            f"{STAGE_LABELS.get(stage, stage)}: {counts[stage]}" for stage in STAGES if stage in counts
        )
        self.summary.configure(text=summary or "pipeline vazio")

    def _move(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        stage = next(
            (key for key, label in STAGE_LABELS.items() if label == self.stage_var.get()), "triagem"
        )
        for imovel_id in selection:
            self.app.store.set_stage(imovel_id, stage)
        self.app.status.set(f"{len(selection)} imovel(is) movido(s) para {stage}.")
        self.refresh()

    def _open(self, _event: Any) -> None:
        selection = self.tree.selection()
        if selection:
            self.app.select_imovel(selection[0])
