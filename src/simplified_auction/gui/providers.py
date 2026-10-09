"""Aba IA: cadastro de provedores, teste de conexao e provedor ativo."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..analyze import run_api
from ..providers import KINDS, Provider, kind_label, load_book, new_id, save_book, to_ai_config

if TYPE_CHECKING:
    from .app import AuctionApp

COLUMNS = (
    ("label", "Nome", 180),
    ("kind", "Tipo", 170),
    ("model", "Modelo", 170),
    ("active", "Ativo", 60),
)

_KIND_BY_LABEL = {kind_label(kind): kind for kind in KINDS}
_TEST_PROMPT = "Responda apenas com a palavra: ok"


class ProvidersView:
    """CRUD de provedores de IA + teste de conexao (feedback visivel)."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.Frame(parent)
        self._editing_id: str | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        columns = ttk.Frame(self.frame)
        columns.pack(fill="both", expand=True, padx=6, pady=6)

        self.tree = ttk.Treeview(
            columns, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse", height=6
        )
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        side = ttk.Frame(columns)
        side.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(side, text="Novo", command=self._new).pack(fill="x", pady=2)
        ttk.Button(side, text="Definir como ativo", command=self._activate).pack(fill="x", pady=2)
        ttk.Button(side, text="Remover", command=self._remove).pack(fill="x", pady=2)

        form = ttk.LabelFrame(self.frame, text="Provedor")
        form.pack(fill="x", padx=6, pady=(0, 6))

        self.label = tk.StringVar()
        self.kind = tk.StringVar(value=kind_label("anthropic"))
        self.model = tk.StringVar()
        self.base_url = tk.StringVar()
        self.api_key = tk.StringVar()
        self.base_url_hint = ttk.Label(form, text="", foreground="#888")

        rows = (
            ("Nome", self.label, False),
            ("Tipo", self.kind, True),
            ("Modelo", self.model, False),
            ("base_url", self.base_url, False),
            ("Chave", self.api_key, True),
        )
        for index, (text, var, _is_choice) in enumerate(rows):
            ttk.Label(form, text=text).grid(row=index, column=0, sticky="w", padx=6, pady=3)
            if text == "Tipo":
                ttk.Combobox(
                    form, textvariable=var, values=[kind_label(k) for k in KINDS],
                    state="readonly", width=34,
                ).grid(row=index, column=1, sticky="w", pady=3)
            elif text == "Chave":
                ttk.Entry(form, textvariable=var, width=52, show="*").grid(
                    row=index, column=1, sticky="w", pady=3
                )
            else:
                ttk.Entry(form, textvariable=var, width=52).grid(
                    row=index, column=1, sticky="w", pady=3
                )
        self.base_url_hint.grid(row=3, column=2, sticky="w", padx=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Salvar", command=self._save).pack(side="left")
        ttk.Button(buttons, text="Testar conexao", command=self._test).pack(side="left", padx=4)
        ttk.Button(buttons, text="Limpar", command=self._new).pack(side="left")

        self.status = ttk.Label(self.frame, text="", foreground="#0a5")
        self.status.pack(anchor="w", padx=6, pady=(0, 6))
        ttk.Label(
            self.frame,
            text=(
                "A chave fica apenas no seu computador (providers.json, permissao 0600). "
                "Sem provedor ativo, o app usa o modo manual (gera o prompt para colar)."
            ),
            foreground="#666",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=6, pady=(0, 6))

    def refresh(self) -> None:
        """Recarrega a lista de provedores."""
        book = load_book()
        self.tree.delete(*self.tree.get_children())
        for provider in book.providers:
            self.tree.insert(
                "", "end", iid=provider.id,
                values=(
                    provider.label or "(sem nome)", kind_label(provider.kind),
                    provider.model or "(padrao)",
                    "sim" if provider.id == book.active else "",
                ),
            )
        active = book.active_provider()
        if active is not None:
            self.status.configure(text=f"Provedor ativo: {active.display}", foreground="#0a5")
        else:
            self.status.configure(
                text="Nenhum provedor ativo — analise no modo manual.", foreground="#a60"
            )

    def _select(self, _event: Any) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        provider = load_book().get(selection[0])
        if provider is None:
            return
        self._editing_id = provider.id
        self.label.set(provider.label)
        self.kind.set(kind_label(provider.kind))
        self.model.set(provider.model)
        self.base_url.set(provider.base_url)
        self.api_key.set(provider.api_key)

    def _new(self) -> None:
        self._editing_id = None
        self.label.set("")
        self.kind.set(kind_label("anthropic"))
        self.model.set("")
        self.base_url.set("")
        self.api_key.set("")
        self.status.configure(text="Preencha e clique em Salvar.", foreground="#666")

    def _current(self) -> Provider:
        kind = _KIND_BY_LABEL.get(self.kind.get(), "anthropic")
        return Provider(
            id=self._editing_id or new_id(),
            kind=kind,
            label=self.label.get().strip(),
            model=self.model.get().strip(),
            base_url=self.base_url.get().strip(),
            api_key=self.api_key.get().strip(),
        )

    def _save(self) -> None:
        provider = self._current()
        if provider.kind != "compatible" and not provider.api_key:
            messagebox.showwarning("IA", "Informe a chave de API (ou use o tipo compativel).")
            return
        book = load_book()
        book.upsert(provider)
        save_book(book)
        self._editing_id = provider.id
        self.status.configure(text=f"Provedor '{provider.display}' salvo.", foreground="#0a5")
        self.refresh()

    def _activate(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        book = load_book()
        book.set_active(selection[0])
        save_book(book)
        self.app.status.set("Provedor de IA ativo atualizado.")
        self.refresh()

    def _remove(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        if not messagebox.askyesno("IA", "Remover este provedor?"):
            return
        book = load_book()
        book.remove(selection[0])
        save_book(book)
        self._new()
        self.refresh()

    def _test(self) -> None:
        config = to_ai_config(self._current())
        if not config.has_api:
            messagebox.showwarning("IA", "Informe a chave para testar.")
            return
        self.status.configure(text="Testando conexao...", foreground="#666")

        def work() -> Any:
            return run_api(config, _TEST_PROMPT)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self.status.configure(text=f"Falhou: {result}", foreground="#b00")
                return
            reply = " ".join(str(result).split())[:200]
            self.status.configure(text=f"OK: {reply}", foreground="#0a5")

        self.app.run_async(work, done)
