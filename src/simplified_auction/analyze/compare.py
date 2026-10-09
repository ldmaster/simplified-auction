"""Compara analises de IA (entre imoveis ou entre editais).

O trabalho aqui e deterministico (sem gastar IA): aponta o que difere, o que e
exclusivo de cada analise e o que elas dizem de diferente. O "porque" vem do
proprio texto da IA (resumo e fundamento de cada risco).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .render import Block

_MAX_VALUE = 46
_SEMAFORO_RANK = {"verde": 0, "amarelo": 1, "vermelho": 2}
_STATUS_LABEL = {"ok": "OK", "atencao": "ATENCAO", "critico": "CRITICO", "nao_consta": "NAO CONSTA"}
_RISCO_LABEL = {"alta": "ALTA", "media": "MEDIA", "baixa": "BAIXA"}

#: Campos simples comparados lado a lado (rotulo, caminho no JSON).
_FIELDS: tuple[tuple[str, str], ...] = (
    ("Tipo de leilao", "tipo_leilao"),
    ("Data do leilao", "data_leilao"),
    ("Valor minimo", "valor_minimo"),
    ("Situacao", "ocupacao.situacao"),
    ("Existe locacao", "ocupacao.existe_locacao"),
)


def _norm(text: Any) -> str:
    normalized = re.sub(r"\W+", " ", str(text or "").lower())
    return normalized.strip()


def _clip(text: Any) -> str:
    value = str(text or "").strip()
    return value if len(value) <= _MAX_VALUE else f"{value[: _MAX_VALUE - 1]}…"


def _get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


@dataclass(slots=True)
class Row:
    """Uma linha da comparacao (campo + um valor por analise)."""

    label: str
    values: list[str]
    different: bool


@dataclass(slots=True)
class Comparison:
    """Resultado da comparacao entre duas ou mais analises."""

    labels: list[str]
    semaforos: list[str]
    rows: list[Row] = field(default_factory=list)
    riscos_so: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    riscos_comuns: list[str] = field(default_factory=list)
    checklist_divergentes: list[Row] = field(default_factory=list)
    resumos: list[str] = field(default_factory=list)

    def melhor(self) -> int | None:
        """Indice da analise com o melhor semaforo (menor risco)."""
        ranks = [
            (_SEMAFORO_RANK.get(value, 9), index)
            for index, value in enumerate(self.semaforos)
        ]
        if not ranks or ranks[0][0] == 9:
            return None
        return min(ranks)[1]


def compare(labels: list[str], results: list[Any]) -> Comparison:
    """Compara analises lado a lado.

    Args:
        labels: Rotulos de cada analise (na ordem).
        results: JSONs das analises (mesma ordem).

    Returns:
        A comparacao, com campos divergentes, riscos exclusivos e o porque.
    """
    data: list[dict[str, Any]] = [item if isinstance(item, dict) else {} for item in results]
    semaforos = [str(item.get("semaforo") or "n/d").strip().lower() for item in data]

    rows: list[Row] = []
    for label, path in _FIELDS:
        values = [_clip(_get(item, path)) or "—" for item in data]
        rows.append(Row(label, values, len({_norm(value) for value in values}) > 1))
    for label, key in (
        ("Formas de pagamento", "formas_pagamento"),
        ("Onus e gravames", "onus_gravames"),
        ("Prazos", "prazos"),
        ("Debitos", "debitos_mencionados"),
    ):
        values = []
        for item in data:
            raw = item.get(key)
            if isinstance(raw, dict):
                text = "; ".join(f"{k}: {v}" for k, v in raw.items() if str(v).strip())
            else:
                text = "; ".join(str(entry) for entry in _as_list(raw) if str(entry).strip())
            values.append(_clip(text) or "—")
        rows.append(Row(label, values, len({_norm(value) for value in values}) > 1))

    riscos_so: dict[str, list[tuple[str, str]]] = {}
    riscos_comuns: list[str] = []
    riscos_por_analise: list[dict[str, str]] = []
    for item in data:
        mapping: dict[str, str] = {}
        for risco in _as_list(item.get("riscos")):
            if isinstance(risco, dict) and str(risco.get("risco") or "").strip():
                mapping[_norm(risco.get("risco"))] = str(risco.get("risco")).strip()
        riscos_por_analise.append(mapping)
    todas = {key for mapping in riscos_por_analise for key in mapping}
    for key in todas:
        presentes = [index for index, mapping in enumerate(riscos_por_analise) if key in mapping]
        if len(presentes) == len(data):
            riscos_comuns.append(riscos_por_analise[presentes[0]][key])
        elif len(presentes) == 1:
            riscos_so.setdefault(labels[presentes[0]], []).append(
                (riscos_por_analise[presentes[0]][key], _gravidade(data[presentes[0]], key))
            )

    checklist: list[Row] = []
    status_por_analise: list[dict[str, str]] = []
    itens: dict[str, str] = {}
    for item in data:
        status_map: dict[str, str] = {}
        for entry in _as_list(item.get("checklist")):
            if isinstance(entry, dict) and str(entry.get("item") or "").strip():
                key = _norm(entry.get("item"))
                status_map[key] = str(entry.get("status") or "").strip().lower()
                itens[key] = str(entry.get("item")).strip()
        status_por_analise.append(status_map)
    for key, texto in itens.items():
        valores = [
            _STATUS_LABEL.get(status_map.get(key, ""), status_map.get(key) or "—")
            for status_map in status_por_analise
        ]
        if len(set(valores)) > 1:
            checklist.append(Row(texto, valores, True))

    resumos = [str(item.get("resumo") or "").strip() for item in data]
    return Comparison(
        labels=labels,
        semaforos=semaforos,
        rows=rows,
        riscos_so=riscos_so,
        riscos_comuns=sorted(riscos_comuns),
        checklist_divergentes=checklist,
        resumos=resumos,
    )


def _gravidade(item: dict[str, Any], chave: str) -> str:
    for risco in _as_list(item.get("riscos")):
        if isinstance(risco, dict) and _norm(risco.get("risco")) == chave:
            return str(risco.get("gravidade") or "").strip().lower()
    return ""


def _table(rows: list[Row], labels: list[str], width: int = 26) -> list[Block]:
    """Monta a tabela de campos como linhas de texto alinhadas."""
    blocks: list[Block] = []
    header = "CAMPO".ljust(width) + " | " + " | ".join(
        label[:20].ljust(20) for label in labels
    )
    blocks.append(Block(header, "h2"))
    for row in rows:
        linha = row.label.ljust(width) + " | " + " | ".join(value.ljust(20) for value in row.values)
        blocks.append(Block(linha, "diff" if row.different else ""))
    return blocks


def to_blocks(comparison: Comparison) -> list[Block]:
    """Renderiza a comparacao em blocos de exibicao (texto + tag)."""
    blocks: list[Block] = [Block(f"COMPARACAO DE {len(comparison.labels)} ANALISES", "h1")]
    blocks.extend(_table(comparison.rows[: len(_FIELDS)], comparison.labels))
    blocks.append(Block("", ""))
    blocks.extend(_table(comparison.rows[len(_FIELDS) :], comparison.labels))

    melhor = comparison.melhor()
    if melhor is not None:
        blocks.append(Block("", ""))
        blocks.append(
            Block(
                f"Menor risco: {comparison.labels[melhor]} "
                f"(semaforo {comparison.semaforos[melhor].upper()})",
                "status_ok",
            )
        )

    for label in comparison.labels:
        exclusivos = comparison.riscos_so.get(label) or []
        if not exclusivos:
            continue
        blocks.append(Block("", ""))
        blocks.append(Block(f"RISCOS SO EM {label}", "h2"))
        for texto, gravidade in exclusivos:
            rotulo = _RISCO_LABEL.get(gravidade, gravidade.upper() or "?")
            blocks.append(Block(f"  [{rotulo}] {texto}", "risco_" + (gravidade or "media")))

    if comparison.riscos_comuns:
        blocks.append(Block("", ""))
        blocks.append(Block(f"RISCOS EM COMUM ({len(comparison.riscos_comuns)})", "h2"))
        for texto in comparison.riscos_comuns:
            blocks.append(Block(f"  • {texto}", "bullet"))

    if comparison.checklist_divergentes:
        blocks.append(Block("", ""))
        blocks.append(Block("CHECKLIST DIVERGENTE", "h2"))
        for row in comparison.checklist_divergentes:
            detalhe = " | ".join(
                f"{label}={value}"
                for label, value in zip(comparison.labels, row.values, strict=True)
            )
            blocks.append(Block(f"  {row.label}: {detalhe}", "diff"))

    blocks.append(Block("", ""))
    blocks.append(Block("POR QUE (resumo de cada analise)", "h2"))
    for label, resumo in zip(comparison.labels, comparison.resumos, strict=True):
        blocks.append(Block(f"  {label}:", "bullet"))
        blocks.append(Block(f"      {resumo or '(sem resumo)'}", "muted"))
    return blocks


def comparison_prompt(comparison: Comparison, results: list[Any]) -> str:
    """Prompt para a IA explicar as diferencas entre as analises."""
    import json

    linhas = [
        "Voce e um advogado imobiliario. Compare as analises abaixo (mesmo lote "
        "de oportunidades ou editais) e explique, em portugues, as DIFERENCAS e o "
        "PORQUE de uma ser mais arriscada/atrativa que a outra.",
        "",
        "Responda em texto curto e direto, com: (1) quadro de diferencas "
        "relevantes; (2) qual e a mais segura e por que; (3) o que verificar "
        "primeiro em cada uma.",
        "",
    ]
    for label, result in zip(comparison.labels, results, strict=True):
        linhas.append(f"=== ANALISE: {label} ===")
        linhas.append(json.dumps(result, ensure_ascii=False, indent=2)[:6000])
        linhas.append("")
    return "\n".join(linhas)
