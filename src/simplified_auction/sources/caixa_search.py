"""Busca ativa no catalogo (endpoints AJAX ``carrega*``).

Os endpoints internos exigem sessao (cookies) e o cabecalho
``X-Requested-With``. Como sao mais frageis, o resultado aqui e apenas a
**lista de ids**; os dados completos saem do catalogo local (lista oficial).
"""

from __future__ import annotations

import logging
import re

from .. import CAIXA_BASE
from ..http import HttpClient

logger = logging.getLogger(__name__)

BUSCA_PAGE_URL = CAIXA_BASE + "/sistema/busca-imovel.asp"
CIDADES_URL = CAIXA_BASE + "/sistema/carregaListaCidades.asp"
PESQUISA_URL = CAIXA_BASE + "/sistema/carregaPesquisaImoveis.asp"

_RE_OPTION = re.compile(r"<option value='([^']*)'>([^<]*)")
_RE_IMOV = re.compile(r"hdnImov\d+'[^>]*value='?([^' >]+)'?")


def _ajax(referer: str) -> dict[str, str]:
    return {"X-Requested-With": "XMLHttpRequest", "Referer": referer}


def bootstrap(client: HttpClient) -> None:
    """Estabelece a sessao (cookies) visitando a pagina de busca."""
    client.get_text(BUSCA_PAGE_URL, encoding="utf-8")


def list_cidades(client: HttpClient, uf: str) -> dict[str, str]:
    """Retorna ``{codigo: nome}`` das cidades de um estado.

    Args:
        client: Cliente HTTP (sessao inicializada).
        uf: Sigla do estado.

    Returns:
        Mapa de codigo para nome da cidade.
    """
    body = client.post_form(
        CIDADES_URL,
        {
            "cmb_estado": uf.upper(),
            "cmb_cidade": "",
            "cmb_tp_venda": "",
            "cmb_tp_imovel": "4",
            "cmb_area_util": "0",
            "cmb_faixa_vlr": "0",
            "cmb_quartos": "0",
            "cmb_vg_garagem": "0",
            "strValorSimulador": "",
            "strAceitaFGTS": "",
            "strAceitaFinanciamento": "",
        },
        headers=_ajax(BUSCA_PAGE_URL),
    )
    return {code: name.strip() for code, name in _RE_OPTION.findall(body) if code}


def _clean_id(token: str) -> str:
    stripped = token.strip().lstrip("0")
    return stripped or token.strip()


def search_ids(
    client: HttpClient,
    *,
    uf: str,
    cidade: str = "",
    bairro: str = "",
    modalidade: str = "",
    tipo: str = "4",
    faixa_valor: str = "0",
) -> list[str]:
    """Resolve os ids de imoveis para um filtro (uma "busca ativa").

    Args:
        client: Cliente HTTP (sessao inicializada).
        uf: Sigla do estado.
        cidade: Codigo da cidade (de ``list_cidades``).
        bairro: Codigo(s) de bairro separados por ``_``.
        modalidade: Codigo da modalidade de venda.
        tipo: Codigo do tipo de imovel (1 Casa, 2 Apto, 3 Outros, 4 Todos).
        faixa_valor: Codigo da faixa de valor.

    Returns:
        Lista de ids de imoveis (sem zeros a esquerda, deduplicada).
    """
    body = client.post_form(
        PESQUISA_URL,
        {
            "hdn_estado": uf.upper(),
            "hdn_cidade": cidade,
            "hdn_bairro": bairro,
            "hdn_tp_venda": modalidade,
            "hdn_tp_imovel": tipo,
            "hdn_area_util": "0",
            "hdn_faixa_vlr": faixa_valor,
            "hdn_quartos": "0",
            "hdn_vg_garagem": "0",
            "strValorSimulador": "",
            "strAceitaFGTS": "",
            "strAceitaFinanciamento": "",
        },
        headers=_ajax(BUSCA_PAGE_URL),
    )
    ids: list[str] = []
    seen: set[str] = set()
    for token in _RE_IMOV.findall(body):
        for raw in token.split("_"):
            imovel_id = _clean_id(raw)
            if imovel_id and imovel_id not in seen:
                seen.add(imovel_id)
                ids.append(imovel_id)
    logger.info("busca ativa em %s retornou %d ids", uf, len(ids))
    return ids
