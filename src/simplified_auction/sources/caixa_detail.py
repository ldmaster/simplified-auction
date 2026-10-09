"""Enriquecimento: parsing da ficha do imovel (``detalhe-imovel.asp``)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from .. import CAIXA_BASE
from ..http import HttpClient
from ..models import Detail
from ..normalize import clean_text, parse_cep, parse_number
from ..store import now_iso

DETAIL_URL = CAIXA_BASE + "/sistema/detalhe-imovel.asp?hdnimovel={imovel_id}"

_RE_VALOR_AVAL = re.compile(r"Valor de avalia[çc][aã]o:\s*R\$\s*([\d.,]+)", re.IGNORECASE)
_RE_VALOR_MIN = re.compile(r"Valor m[íi]nimo de venda:\s*R\$\s*([\d.,]+)", re.IGNORECASE)
_RE_DESCONTO = re.compile(r"desconto de\s*([\d.,]+)\s*%", re.IGNORECASE)
_RE_DOC = re.compile(r"ExibeDoc\('([^']+)'\)")
_RE_FOTO = re.compile(r"/fotos/[^'\"\s>]+\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)


class ParseError(RuntimeError):
    """A pagina recebida nao e uma ficha valida (ex.: desafio anti-bot)."""


def _abs(url: str) -> str:
    if url.startswith("http"):
        return url
    return CAIXA_BASE + (url if url.startswith("/") else f"/{url}")


def _label_strong(container: Tag, label: str) -> str | None:
    wanted = label.lower()
    for span in container.find_all("span"):
        text = span.get_text(" ", strip=True)
        if text.lower().startswith(wanted):
            strong = span.find("strong")
            if strong is not None:
                value = clean_text(strong.get_text(" ", strip=True))
                return value or None
    return None


def _group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def _endereco(container: Tag) -> str | None:
    for paragraph in container.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text.lower().startswith("endere"):
            return clean_text(text.split(":", 1)[1]) if ":" in text else clean_text(text)
    return None


def _pagamento(container: Tag) -> tuple[str | None, str | None]:
    for paragraph in container.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if "FORMAS DE PAGAMENTO" in text.upper():
            upper = text.upper()
            start = upper.index("FORMAS DE PAGAMENTO")
            body = text[start:]
            head, _, tail = body.partition("REGRAS PARA PAGAMENTO DAS DESPESAS")
            formas = head.split(":", 1)[1] if ":" in head else head
            regras = tail.split(":", 1)[1] if ":" in tail else tail
            regras = regras.split("Corretores credenciados")[0]
            return clean_text(formas) or None, clean_text(regras) or None
    return None, None


def parse_detail(html: str, imovel_id: str) -> Detail:
    """Parseia a pagina de ficha de um imovel.

    Args:
        html: HTML da pagina ``detalhe-imovel.asp``.
        imovel_id: Id do imovel (chave).

    Returns:
        A ficha estruturada.
    """
    soup = BeautifulSoup(html, "lxml")
    container = soup.find(id="dadosImovel")
    if not isinstance(container, Tag):
        raise ParseError(
            "A resposta nao contem a ficha do imovel (provavel bloqueio anti-bot)."
        )
    text = container.get_text(" ", strip=True)
    raw = str(container)
    endereco = _endereco(container)
    formas, regras = _pagamento(container)

    doc_match = _RE_DOC.search(raw)
    matricula_url = _abs(doc_match.group(1)) if doc_match else None

    fotos: list[str] = []
    for match in _RE_FOTO.finditer(str(soup)):
        url = _abs(match.group(0))
        if url not in fotos:
            fotos.append(url)

    return Detail(
        imovel_id=imovel_id,
        fetched_at=now_iso(),
        tipo=_label_strong(container, "Tipo de im"),
        situacao=_label_strong(container, "Situa"),
        numero_imovel=_label_strong(container, "Número do im"),
        matricula=_label_strong(container, "Matr"),
        comarca=_label_strong(container, "Comarca"),
        oficio=_label_strong(container, "Ofício") or _label_strong(container, "Of"),
        inscricao_imobiliaria=_label_strong(container, "Inscri"),
        averbacao_leiloes=_label_strong(container, "Averba"),
        valor_avaliacao=parse_number(_group(_RE_VALOR_AVAL, text)),
        valor_minimo=parse_number(_group(_RE_VALOR_MIN, text)),
        desconto=parse_number(_group(_RE_DESCONTO, text)),
        endereco=endereco,
        cep=parse_cep(endereco),
        formas_pagamento=formas,
        regras_despesas=regras,
        matricula_url=matricula_url,
        fotos=tuple(fotos),
    )


def fetch_detail(client: HttpClient, imovel_id: str, *, browser: bool = False) -> Detail:
    """Baixa e parseia a ficha de um imovel.

    Args:
        client: Cliente HTTP.
        imovel_id: Id do imovel.
        browser: Usa o Chromium (Playwright) para resolver o desafio anti-bot.

    Returns:
        A ficha estruturada.

    Raises:
        ParseError: Se a resposta nao for uma ficha (ex.: desafio anti-bot).
        BrowserUnavailable: Se ``browser=True`` e o Playwright faltar.
    """
    url = DETAIL_URL.format(imovel_id=imovel_id)
    if browser:
        from ..browser import fetch_html

        html = fetch_html(url)
    else:
        html = client.get_text(url, encoding="utf-8")
    return parse_detail(html, imovel_id)
