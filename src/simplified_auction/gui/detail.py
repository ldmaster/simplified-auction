"""Aba Ficha: detalhe do imovel, viabilidade, due diligence e analise por IA."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Any

from ..models import STAGE_LABELS, STAGES
from ..sources.caixa_detail import fetch_detail
from ..viability import ViabilityInput, compute
from . import state
from .analysis import AnalysisView
from .analyze_dialog import auto_analyze, open_analyze_dialog
from .external import ExternalView
from .maps import MapPanel
from .photos import PhotoGallery
from .theme import semaforo_colors

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
        self.semaforo_label = tk.Label(top, text="", font=("", 11, "bold"), padx=8)
        self.semaforo_label.pack(side="left", padx=10)
        ttk.Button(top, text="Enriquecer ficha", command=self._enrich).pack(side="right")
        ttk.Button(top, text="Baixar matricula", command=self._download_matricula).pack(side="right", padx=4)
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

        inner = ttk.Notebook(right)
        inner.pack(fill="both", expand=True, pady=6)

        self.analysis_view = AnalysisView(inner, self.app)
        inner.add(self.analysis_view.frame, text="Analise IA")

        checklist = ttk.Frame(inner)
        self.check = ttk.Treeview(
            checklist, columns=("item", "status"), show="headings", height=12
        )
        self.check.heading("item", text="Item")
        self.check.heading("status", text="Status")
        self.check.column("item", width=300)
        self.check.column("status", width=90)
        self.check.pack(fill="both", expand=True)
        self.check.bind("<Double-1>", self._toggle_check)
        inner.add(checklist, text="Due diligence")

        media = ttk.Frame(inner)
        self.gallery = PhotoGallery(media, self.app)
        self.gallery.frame.pack(fill="both", expand=True)
        self.map_panel = MapPanel(media, self.app)
        self.map_panel.frame.pack(fill="x", pady=(6, 0))
        inner.add(media, text="Fotos & mapa")

        self.external_view = ExternalView(inner, self.app)
        inner.add(self.external_view.frame, text="Dados externos")

        self.media_tabs = inner

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
        self.analysis_view.set_scope(imovel_id=imovel_id)
        self._update_semaforo_badge()
        self.gallery.set_urls(list((self._detail or {}).get("fotos") or []))
        self.map_panel.set_property(row, self._detail)
        self.external_view.set_imovel(imovel_id)

    def _update_semaforo_badge(self) -> None:
        """Pinta o selo de semaforo da analise mais recente no cabecalho."""
        cores = semaforo_colors()
        semaforo = self.analysis_view.latest_semaforo()
        if semaforo in cores:
            self.semaforo_label.configure(
                text=f" IA: {semaforo.upper()} ", background=cores[semaforo], foreground="white"
            )
        else:
            self.semaforo_label.configure(
                text=" sem analise IA ", background="#e8e8e8", foreground="#666"
            )

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

        self.app.run_async(work, self._on_enriched, label=f"Buscando ficha de {imovel_id}")

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

        self.app.run_async(work, self._on_matricula, label=f"Baixando matricula de {imovel_id}")

    def _on_matricula(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao baixar a matricula: {result}")
            messagebox.showerror(
                "Matricula", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
            return
        self.app.status.set(f"Matricula salva: {result}")

    def _on_enriched(self, result: Any) -> None:
        if isinstance(result, Exception):
            self.app.status.set(f"Falhou ao buscar a ficha: {result}")
            messagebox.showerror(
                "Enriquecer", f"{result}\n\nDetalhes no log:\n{self.app.log_path()}"
            )
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
        if state.auto_analyze():
            auto_analyze(self.app, imovel_id=self.imovel_id, on_saved=self._on_analysis_saved)
            return
        open_analyze_dialog(self.app, imovel_id=self.imovel_id, on_saved=self._on_analysis_saved)

    def _on_analysis_saved(self) -> None:
        self.analysis_view.set_scope(imovel_id=self.imovel_id)
        self._update_semaforo_badge()
        self.media_tabs.select(self.analysis_view.frame)
        self.app.notebook.select(self.frame)


