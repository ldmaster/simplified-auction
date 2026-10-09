"""Dialogo de analise por IA, reutilizado pela Ficha do imovel e pela aba Editais."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from ..analyze import AIError, prepare, run_api, store_result

if TYPE_CHECKING:
    from .app import AuctionApp


def _order_documents(app: AuctionApp, imovel_id: str | None) -> list[dict[str, Any]]:
    """PDFs baixados; os do imovel escolhido vem primeiro."""
    docs = [doc for doc in app.store.list_documents(limit=500) if doc.get("local_path")]
    if not imovel_id:
        return docs
    mine = [doc for doc in docs if str(doc.get("imovel_id") or "") == str(imovel_id)]
    return mine + [doc for doc in docs if doc not in mine]


def open_analyze_dialog(
    app: AuctionApp,
    *,
    imovel_id: str | None = None,
    preselect: list[int] | None = None,
    on_saved: Callable[[], None] | None = None,
) -> tk.Toplevel:
    """Abre o dialogo de analise (gera o prompt e/ou envia para a IA).

    Args:
        app: Aplicacao (store, config e servico de thread).
        imovel_id: Imovel alvo; ``None`` para analisar apenas documentos.
        preselect: Ids de documentos ja marcados.
        on_saved: Callback chamada apos salvar a analise.

    Returns:
        A janela criada.
    """
    ordered = _order_documents(app, imovel_id)
    preset = set(preselect or [])
    if not preset and imovel_id:
        preset = {
            int(doc["id"])
            for doc in ordered
            if str(doc.get("imovel_id") or "") == str(imovel_id)
        }

    titulo = f"Analise por IA — {imovel_id}" if imovel_id else "Analise por IA — publicacao"
    window = tk.Toplevel(app.root)
    window.title(titulo)
    window.geometry("900x680")

    ttk.Label(
        window,
        text=(
            "Documentos a considerar (use Ctrl/Cmd para escolher varios). "
            + (
                "Os do proprio imovel (matricula) ja vem marcados:"
                if imovel_id
                else "Marque o edital/aviso que quer analisar:"
            )
        ),
    ).pack(anchor="w", padx=6, pady=(6, 0))
    if not ordered:
        ttk.Label(
            window,
            text="Nenhum PDF baixado ainda — use 'Baixar PDFs' (aba Editais) ou 'Baixar matricula' (Ficha).",
            foreground="#b60",
        ).pack(anchor="w", padx=6)

    listbox = tk.Listbox(window, selectmode="extended", height=6, exportselection=False)
    for doc in ordered:
        same = bool(imovel_id) and str(doc.get("imovel_id") or "") == str(imovel_id)
        tag = "deste imovel" if same else str(doc.get("tipo") or "")
        listbox.insert("end", f"{doc['id']} — {doc['nome']}  [{tag}]")
    for index, doc in enumerate(ordered):
        if int(doc["id"]) in preset:
            listbox.selection_set(index)
    listbox.pack(fill="x", padx=6)

    chosen = tk.StringVar(value="")
    ttk.Label(window, textvariable=chosen, foreground="#666").pack(anchor="w", padx=6)

    def selected_ids() -> list[int]:
        return [int(ordered[i]["id"]) for i in listbox.curselection()]

    def update_chosen() -> None:
        ids = selected_ids()
        chosen.set(
            "selecionados: "
            + (", ".join(str(value) for value in ids) if ids else "nenhum (so a ficha)")
        )

    listbox.bind("<<ListboxSelect>>", lambda _event: update_chosen())
    update_chosen()

    ttk.Label(window, text="Prompt / resposta:").pack(anchor="w", padx=6, pady=(6, 0))
    text = scrolledtext.ScrolledText(window, wrap="word")
    text.pack(fill="both", expand=True, padx=6, pady=6)

    def build() -> None:
        ids = selected_ids()
        try:
            prepared = (
                prepare(app.store, imovel_id, document_ids=ids)
                if ids
                else prepare(app.store, imovel_id, text="")
            )
        except AIError as exc:
            messagebox.showwarning("Analise", str(exc))
            return
        text.delete("1.0", "end")
        text.insert("1.0", prepared.prompt)
        window.prompt = prepared.prompt  # type: ignore[attr-defined]
        window.document_ids = prepared.document_ids  # type: ignore[attr-defined]
        if prepared.truncated:
            app.status.set("Aviso: texto truncado no limite do prompt.")

    def run() -> None:
        prompt = getattr(window, "prompt", text.get("1.0", "end").strip())
        ai = app.ai_config()
        if not ai.has_api:
            window.clipboard_clear()
            window.clipboard_append(prompt)
            messagebox.showinfo(
                "Modo manual",
                "Prompt copiado. Cole no ChatGPT/Claude/Gemini e traga a resposta de "
                "volta (cole abaixo e clique em 'Salvar analise').",
            )
            return

        def work() -> Any:
            return run_api(ai, prompt)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                app.status.set(f"Falhou a chamada de IA: {result}")
                messagebox.showerror("IA", f"{result}\n\nDetalhes no log:\n{app.log_path()}")
                return
            text.delete("1.0", "end")
            text.insert("1.0", str(result))
            app.status.set("Resposta recebida. Revise e salve.")

        app.run_async(work, done, label="Consultando a IA")

    def save() -> None:
        raw = text.get("1.0", "end").strip()
        if not raw:
            return
        prompt = getattr(window, "prompt", raw)
        doc_ids = getattr(window, "document_ids", selected_ids())
        ai = app.ai_config()
        _, result = store_result(
            app.store, imovel_id=imovel_id, document_ids=doc_ids,
            provider=ai.provider if ai.has_api else "manual",
            model=ai.model, prompt=prompt, raw=raw,
        )
        app.status.set(f"Analise salva: semaforo {result.get('semaforo', 'n/d')}.")
        if on_saved is not None:
            on_saved()
        window.destroy()

    buttons = ttk.Frame(window)
    buttons.pack(fill="x", padx=6, pady=(0, 6))
    ttk.Button(buttons, text="Gerar prompt", command=build).pack(side="left")
    ttk.Button(buttons, text="Copiar / Enviar API", command=run).pack(side="left", padx=4)
    ttk.Button(buttons, text="Salvar analise", command=save).pack(side="left")
    ttk.Button(buttons, text="Fechar", command=window.destroy).pack(side="right")
    return window
