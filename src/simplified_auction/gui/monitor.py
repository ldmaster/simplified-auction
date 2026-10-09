"""Aba Monitor: verifica novidades de tempos em tempos e notifica."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from .. import notify
from .. import uistate as state
from ..changes import kind_label, summary
from ..sources.caixa_csv import UFS
from ..store import now_iso
from ..sync import sync_lista

if TYPE_CHECKING:
    from .app import AuctionApp

COLUMNS = (
    ("quando", "Quando", 140),
    ("tipo", "Tipo", 130),
    ("imovel", "Imovel", 110),
    ("detalhe", "Detalhe", 470),
)

_MIN_MINUTES = 5


class MonitorView:
    """Verifica o catalogo em intervalos e avisa o que mudou."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self.enabled = tk.BooleanVar(value=bool(state.get("monitor_enabled", False)))
        self.minutes = tk.StringVar(value=str(state.get("monitor_minutes", 60)))
        self.uf = tk.StringVar(value=str(state.get("monitor_uf", "AC")))
        self.status = tk.StringVar(value="")
        self._after: str | None = None
        self._build()
        self.refresh()
        self._schedule()

    def _build(self) -> None:
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Checkbutton(
            top,
            text="Verificar automaticamente",
            variable=self.enabled,
            command=self._toggle,
        ).pack(side="left")
        ttk.Label(top, text="a cada").pack(side="left", padx=(10, 2))
        ttk.Entry(top, textvariable=self.minutes, width=5).pack(side="left")
        ttk.Label(top, text="min").pack(side="left", padx=(2, 10))
        ttk.Label(top, text="UF").pack(side="left")
        ttk.Combobox(top, textvariable=self.uf, values=UFS, width=8).pack(side="left", padx=(2, 10))
        ttk.Button(top, text="Verificar agora", command=lambda: self._check(manual=True)).pack(
            side="left"
        )

        ttk.Label(
            self.frame,
            textvariable=self.status,
            foreground="#888",
        ).pack(anchor="w", padx=6)

        self.tree = ttk.Treeview(self.frame, columns=[c[0] for c in COLUMNS], show="headings")
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        self.tree.bind("<Double-1>", self._open)

        ttk.Label(
            self.frame,
            text=(
                "O monitor roda enquanto o app estiver aberto. Para vigiar sem abrir a "
                "janela, use a CLI: auction news --sync --uf AC (agende no cron/launchd)."
            ),
            foreground="#888",
            wraplength=980,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(0, 6))

        self.ultima = ttk.Label(self.frame, text="", foreground="#888")
        self.ultima.pack(anchor="w", padx=6, pady=(0, 6))
        self._update_ultima()

    def _update_ultima(self) -> None:
        last = str(state.get("last_check_at") or "")
        self.ultima.configure(
            text=f"Ultima verificacao: {last[:19].replace('T', ' ') or 'nunca'}"
        )

    def _toggle(self) -> None:
        state.put("monitor_enabled", bool(self.enabled.get()))
        state.put("monitor_minutes", self.minutes.get())
        state.put("monitor_uf", self.uf.get())
        if self.enabled.get() and not state.get("last_check_at"):
            # Primeira ativacao: marca o ponto de partida para nao repetir o passado.
            state.put("last_check_at", now_iso())
            self._update_ultima()
        self.status.set(
            "Monitor ligado." if self.enabled.get() else "Monitor desligado."
        )

    def _schedule(self) -> None:
        try:
            minutes = max(int(self.minutes.get() or 60), _MIN_MINUTES)
        except ValueError:
            minutes = 60
        self._after = self.frame.after(minutes * 60_000, self._tick)

    def _tick(self) -> None:
        if self.enabled.get() and not self.app._busy:
            self._check(manual=False)
        self._schedule()

    def refresh(self) -> None:
        """Recarrega a lista de novidades ja registradas."""
        self._render(self.app.store.news_since(None, limit=200))

    def _check(self, *, manual: bool) -> None:
        uf = self.uf.get()
        store = self.app.store
        cfg = self.app.cfg
        since = str(state.get("last_check_at") or "") or None
        state.put("monitor_minutes", self.minutes.get())
        state.put("monitor_uf", uf)

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                sync_lista(store, client, uf)
            return store.news_since(since)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self.status.set(f"Falhou a verificacao: {result}")
                if manual:
                    messagebox.showerror(
                        "Monitor", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
                    )
                return
            state.put("last_check_at", now_iso())
            self._update_ultima()
            self._render(result)
            if result:
                resumo = summary(result)
                self.status.set(f"Novidades: {resumo}")
                notify.notify("simplified-auction — novidades", resumo)
                self.app.status.set(f"Novidades no catalogo: {resumo}")
            else:
                self.status.set("Nada novo.")

        self.app.run_async(work, done, label=f"Verificando novidades ({uf})")

    def _render(self, items: list[dict[str, Any]]) -> None:
        self.tree.delete(*self.tree.get_children())
        for item in items:
            self.tree.insert(
                "", "end", iid=str(item.get("id")),
                values=(
                    str(item.get("created_at") or "")[:19].replace("T", " "),
                    kind_label(str(item.get("kind") or "")),
                    item.get("imovel_id") or "-",
                    item.get("detail") or "",
                ),
            )
        if items:
            self.status.set(f"{len(items)} novidade(s) registrada(s).")

    def _open(self, _event: Any) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        imovel_id = str(values[2]) if len(values) > 2 else ""
        if imovel_id and imovel_id != "-" and self.app.store.get_property(imovel_id):
            self.app.select_imovel(imovel_id)
