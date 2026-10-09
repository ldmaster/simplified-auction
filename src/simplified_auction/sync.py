"""Orquestracao da coleta: lista oficial, enriquecimento e diff."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .http import HttpClient
from .sources.caixa_csv import fetch_lista
from .sources.caixa_detail import fetch_detail
from .sources.caixa_docs import save_matricula
from .store import Store, UpsertResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncResult:
    """Resumo de uma sincronizacao da lista oficial."""

    uf: str
    fetched: int
    upsert: UpsertResult


@dataclass(slots=True)
class EnrichResult:
    """Resumo de um enriquecimento de fichas."""

    requested: int = 0
    fetched: int = 0
    failed: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MatriculaResult:
    """Resumo do download de matriculas (PDF)."""

    requested: int = 0
    saved: int = 0
    failed: list[str] = field(default_factory=list)


def sync_lista(store: Store, client: HttpClient, uf: str) -> SyncResult:
    """Baixa a lista oficial de um estado e grava o snapshot no store.

    Args:
        store: Repositorio SQLite.
        client: Cliente HTTP.
        uf: Sigla do estado ou ``geral``.

    Returns:
        O resumo da sincronizacao com o diff.
    """
    properties = fetch_lista(client, uf)
    result = store.upsert_properties(properties)
    store.add_snapshot(f"lista:{uf}", len(properties))
    logger.info("lista %s: %d imoveis coletados", uf, len(properties))
    return SyncResult(uf=uf, fetched=len(properties), upsert=result)


def enrich(
    store: Store,
    client: HttpClient,
    *,
    uf: str | None = None,
    min_desconto: float | None = None,
    limit: int = 50,
    force: bool = False,
    browser: bool = False,
) -> EnrichResult:
    """Enriquece a ficha dos imoveis candidatos (maior desconto primeiro).

    Args:
        store: Repositorio SQLite.
        client: Cliente HTTP.
        uf: Restringe a um estado.
        min_desconto: Considera apenas imoveis com desconto >= este valor.
        limit: Numero maximo de fichas a buscar.
        force: Rebusca mesmo os que ja tem ficha.
        browser: Usa o Chromium para passar pelo desafio anti-bot das paginas
            ``/sistema/`` (requer o extra ``browser``).

    Returns:
        O resumo do enriquecimento.
    """
    detailed = set() if force else store.detailed_ids()
    candidates = store.list_properties(
        uf=uf, min_desconto=min_desconto, order_by="desconto DESC"
    )
    picked = [row for row in candidates if str(row["imovel_id"]) not in detailed][:limit]
    result = EnrichResult(requested=len(picked))
    for row in picked:
        imovel_id = str(row["imovel_id"])
        try:
            detail = fetch_detail(client, imovel_id, browser=browser)
        except Exception as exc:
            logger.warning("falha ao buscar ficha de %s: %s", imovel_id, exc)
            result.failed.append(imovel_id)
            continue
        store.save_detail(detail)
        result.fetched += 1
    logger.info("enriquecidas %d de %d fichas", result.fetched, result.requested)
    return result


def fetch_matriculas(
    store: Store,
    client: HttpClient,
    *,
    uf: str | None = None,
    min_desconto: float | None = None,
    limit: int = 20,
    force: bool = False,
) -> MatriculaResult:
    """Baixa os PDFs das matriculas dos imoveis candidatos.

    A matricula e um asset estatico (``/editais/matricula/``), derivavel do id
    do imovel, e nao passa pela protecao anti-bot.

    Args:
        store: Repositorio SQLite.
        client: Cliente HTTP.
        uf: Restringe a um estado.
        min_desconto: Considera apenas imoveis com desconto >= este valor.
        limit: Numero maximo de matriculas a baixar.
        force: Rebaixa mesmo as que ja existem.

    Returns:
        O resumo dos downloads.
    """
    have: set[str] = set()
    if not force:
        have = {
            str(doc["imovel_id"])
            for doc in store.list_documents(tipo="Matricula")
            if doc.get("local_path") and doc.get("imovel_id")
        }
    candidates = store.list_properties(
        uf=uf, min_desconto=min_desconto, order_by="desconto DESC"
    )
    picked = [row for row in candidates if str(row["imovel_id"]) not in have][:limit]
    result = MatriculaResult(requested=len(picked))
    for row in picked:
        imovel_id = str(row["imovel_id"])
        try:
            save_matricula(client, store, uf=str(row["uf"]), imovel_id=imovel_id)
        except Exception as exc:
            logger.warning("falha ao baixar matricula de %s: %s", imovel_id, exc)
            result.failed.append(imovel_id)
            continue
        result.saved += 1
    logger.info("matriculas: %d de %d", result.saved, result.requested)
    return result
