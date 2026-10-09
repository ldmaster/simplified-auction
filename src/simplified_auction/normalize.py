"""Normalizacao de texto e numeros no formato brasileiro."""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

_MONEY_CLEAN = re.compile(r"[^\d.,-]")
_AREA_TOTAL = re.compile(r"([\d.,]+)\s*de\s*[aá]rea\s*total", re.IGNORECASE)
_AREA_PRIV = re.compile(r"([\d.,]+)\s*de\s*[aá]rea\s*privativa", re.IGNORECASE)
_AREA_TERR = re.compile(r"([\d.,]+)\s*de\s*[aá]rea\s*do\s*terreno", re.IGNORECASE)
_QUARTOS = re.compile(r"(\d+)\s*qto\(s\)", re.IGNORECASE)
_SALAS = re.compile(r"(\d+)\s*sala\(s\)", re.IGNORECASE)
_VAGAS = re.compile(r"(\d+)\s*vaga\(s\)", re.IGNORECASE)
_WC = re.compile(r"\bWC\b")
_CEP = re.compile(r"CEP[:\s]*([\d]{5}-?[\d]{3})", re.IGNORECASE)


def decode_latin1(data: bytes) -> str:
    """Decodifica bytes do site da Caixa (ISO-8859-1/cp1252)."""
    return data.decode("cp1252", errors="replace")


def clean_text(value: str) -> str:
    """Colapsa espacos repetidos e remove espacos nas pontas."""
    return re.sub(r"\s+", " ", value).strip()


def ascii_fold(value: str) -> str:
    """Remove acentos e caixa para comparacoes de cabecalho/rotulo."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", stripped.lower()).strip("_")


def parse_number(value: str | None) -> float | None:
    """Converte numero em texto para float, aceitando os dois separadores.

    Aceita ``"50.074,26"`` (ponto de milhar + virgula decimal) e ``"66.62"``
    (ponto decimal). Retorna ``None`` quando nao ha numero.

    Args:
        value: Texto de entrada.

    Returns:
        O valor convertido ou ``None``.
    """
    if value is None:
        return None
    cleaned = _MONEY_CLEAN.sub("", value).strip()
    if not cleaned or cleaned in {"-", ".", ","}:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = "".join(parts)
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_money(value: str | None) -> float | None:
    """Alias legivel para valores monetarios (``R$ 150.000,00``)."""
    return parse_number(value)


def format_brl(value: float) -> str:
    """Formata um numero como reais no padrao brasileiro (``R$ 1.234,56``)."""
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_cep(value: str | None) -> str | None:
    """Extrai um CEP de um texto (com ou sem hifen)."""
    if not value:
        return None
    match = _CEP.search(value)
    if not match:
        return None
    digits = match.group(1).replace("-", "")
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 8 else digits


def _num(value: str | None) -> float | None:
    return parse_number(value)


class DescricaoExtra(TypedDict):
    """Campos extraidos da descricao do catalogo."""

    tipo: str | None
    area_total: float | None
    area_privativa: float | None
    area_terreno: float | None
    quartos: int | None
    salas: int | None
    vagas: int | None
    wc: int
    cozinha: bool
    area_servico: bool


def parse_descricao(descricao: str) -> DescricaoExtra:
    """Extrai campos estruturados da descricao do catalogo da Caixa.

    Exemplo de entrada:
        ``"Casa, 111.70 de area total, 111.70 de area privativa, 300.00 de
        area do terreno,  1 qto(s), a.serv, WC, 1 sala(s), cozinha,
        1 vaga(s) de garagem."``

    Args:
        descricao: Texto bruto da coluna ``Descricao``.

    Returns:
        Dicionario com ``tipo``, areas, quartos, salas, vagas, ``wc``,
        ``cozinha`` e ``area_servico``.
    """
    text = clean_text(descricao)
    tipo = clean_text(text.split(",", 1)[0]) if text else ""
    total = _AREA_TOTAL.search(text)
    priv = _AREA_PRIV.search(text)
    terr = _AREA_TERR.search(text)
    quartos = _QUARTOS.search(text)
    salas = _SALAS.search(text)
    vagas = _VAGAS.search(text)
    return DescricaoExtra(
        tipo=tipo.title() if tipo else None,
        area_total=_num(total.group(1)) if total else None,
        area_privativa=_num(priv.group(1)) if priv else None,
        area_terreno=_num(terr.group(1)) if terr else None,
        quartos=int(quartos.group(1)) if quartos else None,
        salas=int(salas.group(1)) if salas else None,
        vagas=int(vagas.group(1)) if vagas else None,
        wc=len(_WC.findall(text)),
        cozinha="cozinha" in text.lower(),
        area_servico="a.serv" in text.lower(),
    )
