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
from .scoring import with_score
from .sources import caixa_csv, caixa_docs, caixa_search
from .store import Store
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
    p_analyze.add_argument("--documento", type=int, default=None)
    p_analyze.add_argument("--provider", default=None)
    p_analyze.add_argument("--model", default=None)
    p_analyze.add_argument("--manual", action="store_true", help="So gera o prompt.")
    p_analyze.add_argument("--out", type=Path, default=None, help="Salva o prompt/resposta.")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_gui = sub.add_parser("gui", help="Abre a interface grafica.")
    p_gui.set_defaults(func=_cmd_gui)

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
    with _open_db(cfg) as store:
        try:
            prepared = prepare(store, args.imovel_id, document_id=args.documento)
        except AIError as exc:
            print(f"erro: {exc}")
            return 1
        if args.manual or not cfg.ai.has_api:
            print(prepared.prompt)
            if args.out:
                args.out.write_text(prepared.prompt, encoding="utf-8")
            print("\n[modo manual] cole o prompt acima em um chat de IA.", file=sys.stderr)
            return 0
        assert cfg.ai.api_key is not None
        raw = run_api(cfg.ai, prepared.prompt, provider=args.provider, model=args.model)
        analysis_id, result = store_result(
            store, imovel_id=args.imovel_id, document_id=args.documento,
            provider=args.provider or cfg.ai.provider, model=args.model or cfg.ai.model,
            prompt=prepared.prompt, raw=raw,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nanalise #{analysis_id} gravada.", file=sys.stderr)
    return 0


def _cmd_gui(args: argparse.Namespace, cfg: config_module.Config) -> int:
    from .gui import main as gui_main

    return gui_main(cfg)


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
