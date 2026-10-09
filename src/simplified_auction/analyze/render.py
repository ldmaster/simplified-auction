"""Converte o JSON da analise em linhas prontas para exibicao (com cores).

A logica aqui e pura (sem Tk) para poder ser testada; a GUI so aplica as tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Tag por semaforo.
SEMAFORO_TAGS: dict[str, str] = {
    "verde": "semaforo_verde",
    "amarelo": "semaforo_amarelo",
    "vermelho": "semaforo_vermelho",
}

#: Tag por gravidade de risco.
RISCO_TAGS: dict[str, str] = {
    "alta": "risco_alta",
    "media": "risco_media",
    "baixa": "risco_baixa",
}

#: Tag por status de item do checklist.
STATUS_TAGS: dict[str, str] = {
    "ok": "status_ok",
    "atencao": "status_atencao",
    "critico": "status_critico",
    "nao_consta": "status_nao_consta",
}

_RISCO_LABEL = {"alta": "ALTA", "media": "MEDIA", "baixa": "BAIXA"}
_STATUS_LABEL = {
    "ok": "OK",
    "atencao": "ATENCAO",
    "critico": "CRITICO",
    "nao_consta": "NAO CONSTA",
}
_DEBITO_LABEL = {"iptu": "IPTU/ITR", "condominio": "Condominio", "outros": "Outros"}


@dataclass(frozen=True, slots=True)
class Block:
    """Uma linha da analise: texto + tag de estilo."""

    text: str
    tag: str = ""


def semaforo_tag(value: Any) -> str:
    """Tag de estilo para um semaforo (ou string vazia)."""
    return SEMAFORO_TAGS.get(str(value or "").strip().lower(), "")


def risco_tag(value: Any) -> str:
    """Tag de estilo para uma gravidade de risco."""
    return RISCO_TAGS.get(str(value or "").strip().lower(), "risco_media")


def status_tag(value: Any) -> str:
    """Tag de estilo para um status de checklist."""
    return STATUS_TAGS.get(str(value or "").strip().lower(), "status_nao_consta")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _field(blocks: list[Block], label: str, value: Any) -> None:
    text = _text(value)
    if text:
        blocks.append(Block(f"{label}: {text}", ""))


def _list_section(blocks: list[Block], title: str, value: Any) -> None:
    items = [item for item in _as_list(value) if _text(item)]
    if not items:
        return
    blocks.append(Block("", ""))
    blocks.append(Block(title, "h2"))
    for item in items:
        blocks.append(Block(f"  • {_text(item)}", "bullet"))


def _mapper(result: Any) -> dict[str, Any]:
    return result if isinstance(result, dict) else {}


def render(result: Any, *, meta: str = "") -> list[Block]:
    """Transforma o resultado da IA em blocos de exibicao.

    Args:
        result: Dicionario retornado pela IA (ou ``{"raw": texto}``).
        meta: Linha de contexto (provedor, data, documentos).

    Returns:
        A lista de blocos, na ordem de exibicao.
    """
    data = _mapper(result)
    blocks: list[Block] = []

    semaforo = str(data.get("semaforo") or "").strip().lower()
    if semaforo:
        blocks.append(
            Block(f"  SEMAFORO: {semaforo.upper()}  ", semaforo_tag(semaforo) or "muted")
        )
    if meta:
        blocks.append(Block(meta, "muted"))

    resumo = _text(data.get("resumo"))
    if resumo:
        blocks.append(Block("", ""))
        blocks.append(Block(resumo, ""))

    if _text(data.get("tipo_leilao")) or _text(data.get("valor_minimo")):
        blocks.append(Block("", ""))
        blocks.append(Block("LEILAO", "h2"))
        _field(blocks, "  Tipo", data.get("tipo_leilao"))
        _field(blocks, "  Data", data.get("data_leilao"))
        _field(blocks, "  Valor minimo", data.get("valor_minimo"))

    _list_section(blocks, "FORMAS DE PAGAMENTO", data.get("formas_pagamento"))

    debitos = data.get("debitos_mencionados")
    if isinstance(debitos, dict) and any(_text(value) for value in debitos.values()):
        blocks.append(Block("", ""))
        blocks.append(Block("DEBITOS MENCIONADOS", "h2"))
        for key, value in debitos.items():
            if _text(value):
                blocks.append(
                    Block(f"  • {_DEBITO_LABEL.get(str(key), str(key))}: {_text(value)}", "bullet")
                )

    ocupacao = data.get("ocupacao")
    if isinstance(ocupacao, dict) and any(_text(value) for value in ocupacao.values()):
        blocks.append(Block("", ""))
        blocks.append(Block("OCUPACAO", "h2"))
        for key, label in (("situacao", "Situacao"), ("existe_locacao", "Existe locacao")):
            if _text(ocupacao.get(key)):
                blocks.append(Block(f"  • {label}: {_text(ocupacao.get(key))}", "bullet"))

    _list_section(blocks, "ONUS E GRAVAMES", data.get("onus_gravames"))
    _list_section(blocks, "PRAZOS", data.get("prazos"))

    riscos = [item for item in _as_list(data.get("riscos")) if isinstance(item, dict)]
    if riscos:
        blocks.append(Block("", ""))
        blocks.append(Block("RISCOS", "h2"))
        for risco in riscos:
            gravidade = str(risco.get("gravidade") or "").strip().lower()
            rotulo = _RISCO_LABEL.get(gravidade, gravidade.upper() or "?")
            blocks.append(
                Block(f"  [{rotulo}] {_text(risco.get('risco'))}", risco_tag(gravidade))
            )
            if _text(risco.get("fundamento")):
                blocks.append(Block(f"      {_text(risco.get('fundamento'))}", "muted"))

    checklist = [item for item in _as_list(data.get("checklist")) if isinstance(item, dict)]
    if checklist:
        blocks.append(Block("", ""))
        blocks.append(Block("CHECKLIST DE DUE DILIGENCE", "h2"))
        for entry in checklist:
            status = str(entry.get("status") or "").strip().lower()
            rotulo = _STATUS_LABEL.get(status, status.upper() or "?")
            blocks.append(Block(f"  [{rotulo}] {_text(entry.get('item'))}", status_tag(status)))
            if _text(entry.get("observacao")):
                blocks.append(Block(f"      {_text(entry.get('observacao'))}", "muted"))

    if _text(data.get("raw")):
        blocks.append(Block("", ""))
        blocks.append(Block("A IA nao retornou JSON; texto bruto:", "h2"))
        blocks.append(Block(_text(data.get("raw")), "mono"))

    if len(blocks) <= (1 if meta else 0):
        blocks.append(Block("(analise vazia)", "muted"))
    return blocks
