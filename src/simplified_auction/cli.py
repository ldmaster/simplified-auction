"""Interface de linha de comando do simplified-auction."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__, logging_setup
from . import config as config_module
from .analyze import AIError, prepare, run_api, store_result
from .http import HttpClient, HttpError
from .models import DOCUMENT_TYPES
from .providers import (
    KINDS,
    Provider,
    load_book,
    new_id,
    resolve_ai_config,
    save_book,
    to_ai_config,
)
from .scoring import with_score
from .sources import caixa_csv, caixa_docs, caixa_search
from .store import Store, now_iso
from .sync import enrich, fetch_matriculas, sync_lista

EXPORT_COLUMNS = (
    "imovel_id", "uf", "cidade", "bairro", "endereco", "tipo", "modalidade",
    "preco", "valor_avaliacao", "desconto", "area_privativa", "quartos",
    "vagas", "financiamento", "stage", "link",
)


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser da CLI.

    Returns:
        O parser configurado.
    """
    parser = argparse.ArgumentParser(
        prog="auction",
        description="CRM de leilao de imoveis da Caixa.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--db", type=Path, default=None, help="Caminho do SQLite.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Baixa a lista oficial e grava no banco.")
    p_sync.add_argument("--uf", default="geral", choices=caixa_csv.UFS)
    p_sync.set_defaults(func=_cmd_sync)

    p_enrich = sub.add_parser("enrich", help="Baixa a ficha dos imoveis candidatos.")
    p_enrich.add_argument("--uf", default=None)
    p_enrich.add_argument("--min-desconto", type=float, default=None)
    p_enrich.add_argument("--limit", type=int, default=50)
    p_enrich.add_argument("--force", action="store_true")
    p_enrich.add_argument(
        "--browser", action="store_true",
        help="Usa Chromium (Playwright) para passar pelo desafio anti-bot.",
    )
    p_enrich.set_defaults(func=_cmd_enrich)

    p_matricula = sub.add_parser("matricula", help="Baixa os PDFs das matriculas.")
    p_matricula.add_argument("--uf", default=None)
    p_matricula.add_argument("--min-desconto", type=float, default=None)
    p_matricula.add_argument("--limit", type=int, default=20)
    p_matricula.add_argument("--force", action="store_true")
    p_matricula.set_defaults(func=_cmd_matricula)

    p_list = sub.add_parser("list", help="Lista oportunidades.")
    _add_filters(p_list)
    p_list.add_argument("--top", type=int, default=30)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=_cmd_list)

    p_show = sub.add_parser("show", help="Mostra a ficha completa de um imovel.")
    p_show.add_argument("imovel_id")
    p_show.set_defaults(func=_cmd_show)

    p_export = sub.add_parser("export", help="Exporta oportunidades para CSV.")
    _add_filters(p_export)
    p_export.add_argument("--out", type=Path, required=True)
    p_export.set_defaults(func=_cmd_export)

    p_docs = sub.add_parser("docs", help="Publicacoes legais (editais/avisos).")
    docs_sub = p_docs.add_subparsers(dest="docs_command", required=True)
    p_docs_list = docs_sub.add_parser("list", help="Lista documentos publicados.")
    _add_docs_filters(p_docs_list)
    p_docs_list.set_defaults(func=_cmd_docs_list)
    p_docs_fetch = docs_sub.add_parser("fetch", help="Baixa os PDFs dos documentos.")
    _add_docs_filters(p_docs_fetch)
    p_docs_fetch.add_argument("--limit", type=int, default=20)
    p_docs_fetch.set_defaults(func=_cmd_docs_fetch)

    p_search = sub.add_parser("search", help="Busca ativa no site da Caixa.")
    p_search.add_argument("--uf", required=True, choices=caixa_csv.UFS[:-1])
    p_search.add_argument("--cidade", default=None, help="Nome da cidade.")
    p_search.add_argument("--modalidade", default="")
    p_search.add_argument("--tipo", default="4")
    p_search.set_defaults(func=_cmd_search)

    p_analyze = sub.add_parser("analyze", help="Analisa um documento com IA.")
    p_analyze.add_argument("imovel_id")
    p_analyze.add_argument(
        "--documento", type=int, action="append", default=None,
        help="ID de documento (repetivel). Sem isso, usa os documentos do imovel.",
    )
    p_analyze.add_argument("--provider", default=None)
    p_analyze.add_argument("--model", default=None)
    p_analyze.add_argument("--manual", action="store_true", help="So gera o prompt.")
    p_analyze.add_argument("--out", type=Path, default=None, help="Salva o prompt/resposta.")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_news = sub.add_parser("news", help="Novidades do catalogo (novos, preco, documentos).")
    p_news.add_argument("--uf", default=None, choices=caixa_csv.UFS)
    p_news.add_argument("--sync", action="store_true", help="Sincroniza a lista antes de listar.")
    p_news.add_argument("--since", default=None, help="ISO; padrao: ultima verificacao salva.")
    p_news.add_argument("--notify", action="store_true", help="Notifica no sistema.")
    p_news.set_defaults(func=_cmd_news)

    p_gui = sub.add_parser("gui", help="Abre a interface grafica.")
    p_gui.set_defaults(func=_cmd_gui)

    p_ai = sub.add_parser("ai", help="Provedores de IA (analisar dentro do app).")
    ai_sub = p_ai.add_subparsers(dest="ai_command", required=True)
    ai_sub.add_parser("list", help="Lista os provedores cadastrados.").set_defaults(
        func=_cmd_ai_list
    )
    p_ai_add = ai_sub.add_parser("add", help="Cadastra um provedor.")
    p_ai_add.add_argument("--kind", required=True, choices=KINDS)
    p_ai_add.add_argument("--model", default="")
    p_ai_add.add_argument("--key", default="")
    p_ai_add.add_argument("--label", default="")
    p_ai_add.add_argument("--base-url", default="")
    p_ai_add.set_defaults(func=_cmd_ai_add)
    p_ai_use = ai_sub.add_parser("use", help="Define o provedor ativo.")
    p_ai_use.add_argument("id")
    p_ai_use.set_defaults(func=_cmd_ai_use)
    p_ai_rm = ai_sub.add_parser("rm", help="Remove um provedor.")
    p_ai_rm.add_argument("id")
    p_ai_rm.set_defaults(func=_cmd_ai_rm)
    p_ai_test = ai_sub.add_parser("test", help="Testa a conexao com o provedor.")
    p_ai_test.add_argument("--id", default=None)
    p_ai_test.set_defaults(func=_cmd_ai_test)

    return parser


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--uf", default=None)
    parser.add_argument("--cidade", default=None)
    parser.add_argument("--tipo", default=None)
    parser.add_argument("--modalidade", default=None)
    parser.add_argument("--min-desconto", type=float, default=None)
    parser.add_argument("--max-preco", type=float, default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--stage", default=None)


def _add_docs_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--uf", required=True, choices=caixa_csv.UFS[:-1])
    parser.add_argument("--ano", type=int, required=True)
    parser.add_argument("--mes", type=int, required=True)
    parser.add_argument(
        "--tipo", default="9", choices=sorted(DOCUMENT_TYPES),
        help="1..9 (9 = Edital Unico).",
    )
    parser.add_argument(
        "--browser", action="store_true",
        help="Usa Chromium (Playwright) para passar pelo desafio anti-bot.",
    )


def _open_db(cfg: config_module.Config) -> Store:
    return Store(cfg.db_path)


def _client(cfg: config_module.Config) -> HttpClient:
    return HttpClient(cfg.http)


def _cmd_sync(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store, _client(cfg) as client:
        result = sync_lista(store, client, args.uf)
    up = result.upsert
    print(
        f"{result.uf}: {result.fetched} imoveis | novos {len(up.new)}, "
        f"alterados {len(up.changed)}, queda de preco {len(up.price_drop)}, "
        f"inativos {len(up.deactivated)}, inalterados {up.unchanged}"
    )
    return 0


def _cmd_enrich(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store, _client(cfg) as client:
        result = enrich(
            store, client, uf=args.uf, min_desconto=args.min_desconto,
            limit=args.limit, force=args.force,
            browser=bool(args.browser or cfg.http.browser),
        )
    print(f"fichas: {result.fetched}/{result.requested} | falhas {len(result.failed)}")
    return 0


def _cmd_matricula(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store, _client(cfg) as client:
        result = fetch_matriculas(
            store, client, uf=args.uf, min_desconto=args.min_desconto,
            limit=args.limit, force=args.force,
        )
    print(f"matriculas: {result.saved}/{result.requested} | falhas {len(result.failed)}")
    return 0


def _rows(store: Store, args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = store.list_properties(
        uf=args.uf, cidade=getattr(args, "cidade", None), tipo=getattr(args, "tipo", None),
        modalidade=getattr(args, "modalidade", None),
        min_desconto=getattr(args, "min_desconto", None),
        max_preco=getattr(args, "max_preco", None),
        text=getattr(args, "text", None), stage=getattr(args, "stage", None),
    )
    return with_score(rows)


def _cmd_list(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store:
        rows = _rows(store, args)
    if args.json:
        print(json.dumps(rows[: args.top], ensure_ascii=False, indent=2))
        return 0
    print(f"{'score':>6} {'desc%':>6} {'preco':>12} {'uf':>2}  cidade / bairro / tipo")
    for row in rows[: args.top]:
        print(
            f"{row['score']:>6.1f} {float(row['desconto'] or 0):>6.1f} "
            f"{float(row['preco'] or 0):>12,.0f} {str(row['uf']):>2}  "
            f"{row['cidade']} / {row['bairro']} / {row['tipo']}"
        )
    print(f"({len(rows)} imoveis)")
    return 0


def _cmd_show(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store:
        row = store.get_property(args.imovel_id)
        if row is None:
            print(f"imovel {args.imovel_id} nao encontrado")
            return 1
        detail = store.get_detail(args.imovel_id)
        pipeline = store.get_pipeline(args.imovel_id)
        history = store.price_history(args.imovel_id)
    print(json.dumps(
        {"imovel": row, "ficha": detail, "pipeline": pipeline, "historico": history},
        ensure_ascii=False, indent=2,
    ))
    return 0


def _cmd_export(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store:
        rows = _rows(store, args)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"{len(rows)} imoveis exportados para {args.out}")
    return 0


def _cmd_docs_list(args: argparse.Namespace, cfg: config_module.Config) -> int:
    use_browser = bool(args.browser or cfg.http.browser)
    with _open_db(cfg) as store, _client(cfg) as client:
        if not use_browser:
            caixa_docs.bootstrap(client)
        documents = caixa_docs.list_documents(
            client, uf=args.uf, mes=args.mes, ano=args.ano, tipo=args.tipo, browser=use_browser
        )
        for doc in documents:
            store.upsert_document(doc)
    print(f"{len(documents)} documento(s):")
    for doc in documents:
        print(f"  [{doc.ano}/{doc.mes:02d}] {doc.tipo} -> {doc.nome}")
    return 0


def _cmd_docs_fetch(args: argparse.Namespace, cfg: config_module.Config) -> int:
    use_browser = bool(args.browser or cfg.http.browser)
    with _open_db(cfg) as store, _client(cfg) as client:
        if not use_browser:
            caixa_docs.bootstrap(client)
        documents = caixa_docs.list_documents(
            client, uf=args.uf, mes=args.mes, ano=args.ano, tipo=args.tipo, browser=use_browser
        )
        count = 0
        for doc in documents[: args.limit]:
            doc_id = store.upsert_document(doc)
            caixa_docs.download(client, store, doc_id, ajax=False)
            count += 1
    print(f"{count} PDF(s) baixado(s).")
    return 0


def _cmd_search(args: argparse.Namespace, cfg: config_module.Config) -> int:
    with _open_db(cfg) as store, _client(cfg) as client:
        caixa_search.bootstrap(client)
        cidade_code = ""
        if args.cidade:
            cidades = caixa_search.list_cidades(client, args.uf)
            wanted = args.cidade.strip().upper()
            matches = [code for code, name in cidades.items() if wanted in name.upper()]
            if not matches:
                print(f"cidade '{args.cidade}' nao encontrada em {args.uf}")
                return 1
            cidade_code = matches[0]
        ids = caixa_search.search_ids(
            client, uf=args.uf, cidade=cidade_code, modalidade=args.modalidade, tipo=args.tipo
        )
        found = [store.get_property(i) for i in ids]
    print(f"{len(ids)} id(s) na busca ativa em {args.uf}:")
    for imovel_id, row in zip(ids, found, strict=True):
        if row is None:
            print(f"  {imovel_id}  (nao esta no catalogo local; rode sync/enrich)")
        else:
            print(f"  {imovel_id}  {row['cidade']} / {row['bairro']} desc {row['desconto']}%")
    return 0


def _cmd_analyze(args: argparse.Namespace, cfg: config_module.Config) -> int:
    ai = resolve_ai_config()
    with _open_db(cfg) as store:
        doc_ids: list[int] = list(args.documento or [])
        if not doc_ids:
            doc_ids = [
                int(doc["id"])
                for doc in store.list_documents(imovel_id=args.imovel_id)
                if doc.get("local_path")
            ]
        try:
            prepared = prepare(store, args.imovel_id, document_ids=doc_ids)
        except AIError as exc:
            print(f"erro: {exc}")
            print(
                "dica: baixe a matricula com 'auction matricula' ou editais com "
                "'auction docs fetch' e tente de novo.",
                file=sys.stderr,
            )
            return 1
        if prepared.sources:
            print(f"documentos considerados: {'; '.join(prepared.sources)}", file=sys.stderr)
        if prepared.truncated:
            print("aviso: texto truncado no limite do prompt.", file=sys.stderr)
        if args.manual or not ai.has_api:
            print(prepared.prompt)
            if args.out:
                args.out.write_text(prepared.prompt, encoding="utf-8")
            print("\n[modo manual] cole o prompt acima em um chat de IA.", file=sys.stderr)
            return 0
        raw = run_api(ai, prepared.prompt, provider=args.provider, model=args.model)
        analysis_id, result = store_result(
            store, imovel_id=args.imovel_id, document_ids=prepared.document_ids,
            provider=args.provider or ai.provider, model=args.model or ai.model,
            prompt=prepared.prompt, raw=raw,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nanalise #{analysis_id} gravada.", file=sys.stderr)
    return 0


def _cmd_gui(args: argparse.Namespace, cfg: config_module.Config) -> int:
    from .gui import main as gui_main

    return gui_main(cfg)


def _cmd_news(args: argparse.Namespace, cfg: config_module.Config) -> int:
    from . import notify as notify_module
    from . import uistate
    from .changes import kind_label, summary

    since = args.since or uistate.last_check_at()
    with _open_db(cfg) as store:
        if args.sync:
            uf = args.uf or str(uistate.filters("editais").get("uf") or "geral")
            with _client(cfg) as client:
                sync_lista(store, client, uf)
        items = store.news_since(since)
    print(f"{len(items)} novidade(s): {summary(items)}")
    for item in items:
        print(
            f"  [{kind_label(str(item.get('kind') or ''))}] "
            f"{item.get('imovel_id') or '-'} {item.get('detail') or ''}"
        )
    uistate.set_last_check_at(now_iso())
    if args.notify and items:
        notify_module.notify("simplified-auction — novidades", summary(items))
    return 0


def _cmd_ai_list(args: argparse.Namespace, cfg: config_module.Config) -> int:
    book = load_book()
    if not book.providers:
        print("Nenhum provedor cadastrado (modo manual). Use: auction ai add ...")
        return 0
    for provider in book.providers:
        mark = "*" if provider.id == book.active else " "
        key = "sim" if provider.api_key else "nao"
        print(
            f"{mark} {provider.id}  {provider.display}  chave:{key}  "
            f"base_url:{provider.base_url or '-'}"
        )
    print("(* = ativo)")
    return 0


def _cmd_ai_add(args: argparse.Namespace, cfg: config_module.Config) -> int:
    book = load_book()
    provider = Provider(
        id=new_id(), kind=args.kind, label=args.label, model=args.model,
        base_url=args.base_url, api_key=args.key,
    )
    book.upsert(provider)
    save_book(book)
    print(f"cadastrado {provider.id}: {provider.display} (ativo={book.active == provider.id})")
    return 0


def _cmd_ai_use(args: argparse.Namespace, cfg: config_module.Config) -> int:
    book = load_book()
    if book.get(args.id) is None:
        print(f"provedor {args.id} nao encontrado")
        return 1
    book.set_active(args.id)
    save_book(book)
    print(f"ativo agora: {args.id}")
    return 0


def _cmd_ai_rm(args: argparse.Namespace, cfg: config_module.Config) -> int:
    book = load_book()
    if book.get(args.id) is None:
        print(f"provedor {args.id} nao encontrado")
        return 1
    book.remove(args.id)
    save_book(book)
    print(f"removido {args.id}")
    return 0


def _cmd_ai_test(args: argparse.Namespace, cfg: config_module.Config) -> int:
    book = load_book()
    provider = book.get(args.id) if args.id else book.active_provider()
    if provider is None:
        print("nenhum provedor (cadastre com 'auction ai add').")
        return 1
    ai = to_ai_config(provider)
    if not ai.has_api:
        print("provedor sem chave de API.")
        return 1
    try:
        reply = run_api(ai, "Responda apenas com a palavra: ok")
    except AIError as exc:
        print(f"falhou: {exc}")
        return 2
    print(f"OK ({provider.display}): {' '.join(reply.split())[:200]}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI.

    Args:
        argv: Argumentos (usa ``sys.argv`` se omitido).

    Returns:
        O codigo de saida.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    logging_setup.setup()
    cfg = config_module.load(db_path=args.db)
    try:
        return int(args.func(args, cfg))
    except HttpError as exc:
        print(f"erro de rede: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
