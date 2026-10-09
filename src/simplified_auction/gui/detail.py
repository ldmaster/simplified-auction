"""Aba Ficha: detalhe do imovel, viabilidade, due diligence e analise por IA."""

from __future__ import annotations

import json
import tkinter as tk
import webbrowser
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from ..analyze import AIError, prepare, run_api, store_result
from ..models import STAGE_LABELS, STAGES
from ..sources.caixa_detail import fetch_detail
from ..viability import ViabilityInput, compute

if TYPE_CHECKING:
    from .app import AuctionApp

_STATUS_CYCLE = ("pendente", "ok", "atencao", "critico", "nao_consta")
_DASH = "—"


def _money(value: Any) -> str:
    try:
        return f"R$ {float(value):,.2f}"
    except (TypeError, ValueError):
        return _DASH


class DetailView:
    """Ficha completa de um imovel com as ferramentas de decisao."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.imovel_id: str | None = None
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=6, pady=6)
        self.title = ttk.Label(top, text="Selecione um imovel na aba Oportunidades", font=("", 13, "bold"))
        self.title.pack(side="left")
        ttk.Button(top, text="Enriquecer ficha", command=self._enrich).pack(side="right")
        ttk.Button(top, text="Baixar matricula", command=self._download_matricula).pack(side="right", padx=4)
        ttk.Button(top, text="Carregar fotos", command=self._load_current_photos).pack(side="right", padx=4)
        ttk.Button(top, text="Abrir no site", command=self._open_site).pack(side="right")
        ttk.Button(top, text="Analisar com IA", command=self._analyze).pack(side="right", padx=4)

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=6)

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.info = scrolledtext.ScrolledText(left, height=14, wrap="word")
        self.info.pack(fill="both", expand=True)
        self.info.configure(state="disabled")

        controls = ttk.LabelFrame(left, text="Pipeline")
        controls.pack(fill="x", pady=6)
        self.stage = tk.StringVar()
        self.decisao = tk.StringVar()
        self.notas = tk.StringVar()
        ttk.Label(controls, text="Estagio").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            controls, textvariable=self.stage, width=16,
            values=[STAGE_LABELS[s] for s in STAGES], state="readonly",
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(controls, text="Decisao").grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Combobox(
            controls, textvariable=self.decisao, width=12,
            values=["", "avaliar", "propor", "descartar"], state="readonly",
        ).grid(row=0, column=3, sticky="w")
        ttk.Label(controls, text="Notas").grid(row=1, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.notas, width=60).grid(
            row=1, column=1, columnspan=3, sticky="we", pady=4
        )
        ttk.Button(controls, text="Salvar", command=self._save_pipeline).grid(row=2, column=1, sticky="w")

        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        viability = ttk.LabelFrame(right, text="Viabilidade")
        viability.pack(fill="x")
        self.vars: dict[str, tk.StringVar] = {
            name: tk.StringVar() for name in
            ("comissao_pct", "itbi_pct", "reforma", "dividas", "desocupacao", "valor_mercado")
        }
        labels = {
            "comissao_pct": "Comissao %", "itbi_pct": "ITBI %", "reforma": "Reforma R$",
            "dividas": "Dividas R$", "desocupacao": "Desocupacao R$", "valor_mercado": "Valor mercado R$",
        }
        for index, (name, label) in enumerate(labels.items()):
            ttk.Label(viability, text=label).grid(row=index // 2, column=(index % 2) * 2, sticky="w", padx=4)
            ttk.Entry(viability, textvariable=self.vars[name], width=12).grid(
                row=index // 2, column=(index % 2) * 2 + 1, sticky="w", padx=4
            )
        ttk.Button(viability, text="Calcular", command=self._calc_viability).grid(row=3, column=0, sticky="w", pady=4)
        self.viability_result = ttk.Label(viability, text="", foreground="#0a5")
        self.viability_result.grid(row=3, column=1, columnspan=3, sticky="w")

        checklist = ttk.LabelFrame(right, text="Due diligence (duplo clique alterna)")
        checklist.pack(fill="both", expand=True, pady=6)
        self.check = ttk.Treeview(
            checklist, columns=("item", "status"), show="headings", height=12
        )
        self.check.heading("item", text="Item")
        self.check.heading("status", text="Status")
        self.check.column("item", width=320)
        self.check.column("status", width=100)
        self.check.pack(fill="both", expand=True)
        self.check.bind("<Double-1>", self._toggle_check)

        photos = ttk.LabelFrame(right, text="Fotos")
        photos.pack(fill="x")
        self.photos_frame = ttk.Frame(photos)
        self.photos_frame.pack(fill="x")
        self._photo_refs: list[Any] = []

    # ------------------------------------------------------------------ render

    def show(self, imovel_id: str) -> None:
        """Carrega e exibe a ficha de um imovel."""
        self.imovel_id = imovel_id
        row = self.app.store.get_property(imovel_id)
        if row is None:
            self.title.configure(text=f"Imovel {imovel_id} nao encontrado")
            return
        self.title.configure(text=f"{row['imovel_id']} — {row['cidade']}/{row['uf']} — {row['tipo']}")
        self._detail = self.app.store.get_detail(imovel_id)
        self._render(row, self._detail)
        self._load_pipeline()
        self._load_checklist()
        self._prefill_viability(row)
        self._clear_photos()

    def _render(self, row: dict[str, Any], detail: dict[str, Any] | None) -> None:
        lines = [
            f"Tipo: {row['tipo']}   Modalidade: {row['modalidade']}",
            f"Endereco: {row['endereco']}   Bairro: {row['bairro']}",
            f"Preco: {_money(row['preco'])}   Avaliacao: {_money(row['valor_avaliacao'])}"
            f"   Desconto: {row['desconto']}%",
            f"Financiavel: {'sim' if row['financiamento'] else 'nao'}   Link: {row['link']}",
            f"Descricao: {row['descricao']}",
        ]
        if detail is None:
            lines.append("\n[ficha nao enriquecida — clique em 'Enriquecer ficha']")
        else:
            lines += [
                "",
                f"Matricula: {detail.get('matricula')}   Comarca: {detail.get('comarca')}"
                f"   Oficio: {detail.get('oficio')}",
                f"Averbacao leiloes: {detail.get('averbacao_leiloes')}"
                f"   Inscricao: {detail.get('inscricao_imobiliaria')}",
                f"CEP: {detail.get('cep')}   Situacao: {detail.get('situacao')}",
                f"Endereco (ficha): {detail.get('endereco')}",
                f"Formas de pagamento: {detail.get('formas_pagamento')}",
                f"Regras de despesas: {detail.get('regras_despesas')}",
                f"Matricula PDF: {detail.get('matricula_url')}",
                f"Fotos: {len(detail.get('fotos') or [])}",
            ]
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(lines))
        self.info.configure(state="disabled")

    def _load_pipeline(self) -> None:
        if not self.imovel_id:
            return
        pipe = self.app.store.get_pipeline(self.imovel_id)
        self.stage.set(STAGE_LABELS.get(str(pipe["stage"]), "Novo"))
        self.decisao.set(str(pipe["decisao"]))
        self.notas.set(str(pipe["notas"]))

    def _load_checklist(self) -> None:
        self.check.delete(*self.check.get_children())
        if not self.imovel_id:
            return
        for entry in self.app.store.get_checklist(self.imovel_id):
            self.check.insert("", "end", iid=entry["item"], values=(entry["item"], entry["status"]))

    def _prefill_viability(self, row: dict[str, Any]) -> None:
        self.vars["comissao_pct"].set("5")
        self.vars["itbi_pct"].set("3")
        self.vars["valor_mercado"].set(f"{float(row['valor_avaliacao'] or 0):.0f}")
        for name in ("reforma", "dividas", "desocupacao"):
            self.vars[name].set("0")

    # ------------------------------------------------------------------ acoes

    def _label_to_stage(self) -> str:
        wanted = self.stage.get()
        for key, label in STAGE_LABELS.items():
            if label == wanted:
                return key
        return "novo"

    def _save_pipeline(self) -> None:
        if not self.imovel_id:
            return
        self.app.store.set_stage(self.imovel_id, self._label_to_stage())
        self.app.store.set_decisao(self.imovel_id, self.decisao.get())
        self.app.store.set_notas(self.imovel_id, self.notas.get())
        self.app.status.set(f"Pipeline salvo para {self.imovel_id}.")
        self.app.pipeline.refresh()

    def _toggle_check(self, _event: Any) -> None:
        selection = self.check.selection()
        if not selection or not self.imovel_id:
            return
        item = selection[0]
        current = self.check.set(item, "status")
        nxt = _STATUS_CYCLE[(_STATUS_CYCLE.index(current) + 1) % len(_STATUS_CYCLE)] \
            if current in _STATUS_CYCLE else "pendente"
        self.check.set(item, "status", nxt)
        self.app.store.set_checklist_item(self.imovel_id, item, nxt)

    def _enrich(self) -> None:
        if not self.imovel_id:
            return
        imovel_id = self.imovel_id
        cfg = self.app.cfg

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                return fetch_detail(client, imovel_id, browser=cfg.http.browser)

        self.app.status.set(f"Buscando ficha de {imovel_id}...")
        self.app.run_async(work, self._on_enriched)

    def _download_matricula(self) -> None:
        if not self.imovel_id:
            return
        row = self.app.store.get_property(self.imovel_id)
        if row is None:
            return
        imovel_id = self.imovel_id
        uf = str(row["uf"])
        cfg = self.app.cfg
        store = self.app.store

        def work() -> Any:
            from ..http import HttpClient
            from ..sources import caixa_docs

            with HttpClient(cfg.http) as client:
                return caixa_docs.save_matricula(client, store, uf=uf, imovel_id=imovel_id)

        self.app.status.set(f"Baixando matricula de {imovel_id}...")
        self.app.run_async(work, self._on_matricula)

    def _on_matricula(self, result: Any) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Matricula", str(result))
            return
        self.app.status.set(f"Matricula salva: {result}")

    def _on_enriched(self, result: Any) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Enriquecer", str(result))
            return
        self.app.store.save_detail(result)
        self.show(str(result.imovel_id))
        self.app.status.set("Ficha atualizada.")

    def _open_site(self) -> None:
        if not self.imovel_id:
            return
        row = self.app.store.get_property(self.imovel_id)
        if row and row.get("link"):
            webbrowser.open(str(row["link"]))

    def _calc_viability(self) -> None:
        if not self.imovel_id:
            return
        row = self.app.store.get_property(self.imovel_id)
        if row is None:
            return

        def num(name: str) -> float:
            try:
                return float(self.vars[name].get() or 0)
            except ValueError:
                return 0.0

        result = compute(
            ViabilityInput(
                preco=float(row["preco"] or 0),
                valor_avaliacao=float(row["valor_avaliacao"] or 0) or None,
                valor_mercado=num("valor_mercado") or None,
                comissao_pct=num("comissao_pct"),
                itbi_pct=num("itbi_pct"),
                reforma=num("reforma"),
                dividas=num("dividas"),
                desocupacao=num("desocupacao"),
            )
        )
        margem = _money(result.margem) if result.margem is not None else _DASH
        roi = f"{result.roi_pct:.1f}%" if result.roi_pct is not None else _DASH
        self.viability_result.configure(
            text=f"Custo total {_money(result.custo_total)} | margem {margem} | ROI {roi}"
        )

    # ------------------------------------------------------------------ analise IA

    def _analyze(self) -> None:
        if not self.imovel_id:
            messagebox.showinfo("Analise", "Selecione um imovel primeiro.")
            return
        docs = [d for d in self.app.store.list_documents(limit=200) if d.get("local_path")]
        window = tk.Toplevel(self.frame)
        window.title(f"Analise por IA — {self.imovel_id}")
        window.geometry("900x640")

        ttk.Label(window, text="Documento (PDF baixado):").pack(anchor="w", padx=6, pady=(6, 0))
        doc_var = tk.StringVar()
        options = ["(somente ficha)"] + [f"{d['id']} — {d['nome']}" for d in docs]
        combo = ttk.Combobox(window, textvariable=doc_var, values=options, width=80, state="readonly")
        combo.current(0)
        combo.pack(anchor="w", padx=6)

        ttk.Label(window, text="Prompt / resposta:").pack(anchor="w", padx=6, pady=(6, 0))
        text = scrolledtext.ScrolledText(window, wrap="word")
        text.pack(fill="both", expand=True, padx=6, pady=6)

        def selected_doc_id() -> int | None:
            value = doc_var.get()
            if value.startswith("("):
                return None
            return int(value.split(" — ")[0])

        def build() -> None:
            assert self.imovel_id is not None
            try:
                if selected_doc_id() is None:
                    prepared = prepare(self.app.store, self.imovel_id, text="")
                else:
                    prepared = prepare(self.app.store, self.imovel_id, document_id=selected_doc_id())
            except AIError as exc:
                messagebox.showwarning("Analise", str(exc))
                return
            text.delete("1.0", "end")
            text.insert("1.0", prepared.prompt)
            window.prompt = prepared.prompt  # type: ignore[attr-defined]

        def run() -> None:
            prompt = getattr(window, "prompt", text.get("1.0", "end").strip())
            ai = self.app.ai_config()
            if not ai.has_api:
                window.clipboard_clear()
                window.clipboard_append(prompt)
                messagebox.showinfo(
                    "Modo manual",
                    "Prompt copiado. Cole no ChatGPT/Claude web e traga a resposta "
                    "para ca (cole abaixo e clique em 'Salvar analise').",
                )
                return
            self.app.status.set("Consultando a IA...")

            def work() -> Any:
                return run_api(ai, prompt)

            def done(result: Any) -> None:
                if isinstance(result, Exception):
                    messagebox.showerror("IA", str(result))
                    return
                text.delete("1.0", "end")
                text.insert("1.0", str(result))
                self.app.status.set("Resposta recebida. Revise e salve.")

            self.app.run_async(work, done)

        def save() -> None:
            assert self.imovel_id is not None
            raw = text.get("1.0", "end").strip()
            if not raw:
                return
            prompt = getattr(window, "prompt", raw)
            ai = self.app.ai_config()
            _, result = store_result(
                self.app.store, imovel_id=self.imovel_id, document_id=selected_doc_id(),
                provider=ai.provider if ai.has_api else "manual",
                model=ai.model, prompt=prompt, raw=raw,
            )
            self.app.status.set(f"Analise salva: semaforo {result.get('semaforo', 'n/d')}.")
            messagebox.showinfo("Analise", json.dumps(result, ensure_ascii=False, indent=2)[:2000])

        buttons = ttk.Frame(window)
        buttons.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(buttons, text="Gerar prompt", command=build).pack(side="left")
        ttk.Button(buttons, text="Copiar / Enviar API", command=run).pack(side="left", padx=4)
        ttk.Button(buttons, text="Salvar analise", command=save).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=window.destroy).pack(side="right")

    # ------------------------------------------------------------------ fotos

    def _clear_photos(self) -> None:
        for child in self.photos_frame.winfo_children():
            child.destroy()
        self._photo_refs = []

    def _load_current_photos(self) -> None:
        detail = getattr(self, "_detail", None) or {}
        urls = list(detail.get("fotos") or [])
        if not urls:
            messagebox.showinfo("Fotos", "Sem fotos; enriqueça a ficha primeiro.")
            return
        self._load_photos(urls)

    def _load_photos(self, urls: list[str]) -> None:
        from .images import PILLOW_AVAILABLE, thumbnail, to_photoimage

        if not PILLOW_AVAILABLE:
            ttk.Label(self.photos_frame, text="Pillow nao instalado (pip install .[gui])").pack()
            return
        cfg = self.app.cfg

        def work() -> Any:
            from ..http import HttpClient

            out: list[Any] = []
            with HttpClient(cfg.http) as client:
                for url in urls[:6]:
                    try:
                        image = thumbnail(client.get_bytes(url))
                    except Exception:
                        image = None
                    if image is not None:
                        out.append(image)
            return out

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                return
            self._clear_photos()
            for image in result:
                photo = to_photoimage(image)
                if photo is None:
                    continue
                self._photo_refs.append(photo)
                ttk.Label(self.photos_frame, image=photo).pack(side="left", padx=2)

        self.app.run_async(work, done)
