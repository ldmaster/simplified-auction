"""Score de oportunidade (0-100) explicavel."""

from __future__ import annotations

from typing import Any

_TERRENO = {"terreno", "gleba", "gleba urbana", "gleba rural", "area", "lote"}


def _f(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def opportunity_score(row: dict[str, Any]) -> float:
    """Calcula um score 0-100 combinando desconto, liquidez e financiamento.

    Args:
        row: Linha de imovel (com ``desconto``, ``preco``, ``tipo``,
            ``financiamento``).

    Returns:
        O score (maior = mais atrativo).
    """
    desconto = max(min(_f(row.get("desconto")), 90.0), 0.0)
    score = desconto / 90.0 * 70.0
    if row.get("financiamento"):
        score += 10.0
    tipo = str(row.get("tipo") or "").lower()
    if tipo in _TERRENO:
        score *= 0.6
    preco = _f(row.get("preco"))
    if preco > 750_000:
        score -= 5.0
    return round(max(score, 0.0), 1)


def explain(row: dict[str, Any]) -> str:
    """Explica em uma linha os fatores do score."""
    parts: list[str] = [f"desconto {_f(row.get('desconto')):.1f}%"]
    if row.get("financiamento"):
        parts.append("financiavel")
    tipo = str(row.get("tipo") or "").lower()
    if tipo in _TERRENO:
        parts.append("terreno (liquidez menor)")
    return ", ".join(parts)


def with_score(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anota ``score`` e ``score_reason`` em cada linha."""
    for row in rows:
        row["score"] = opportunity_score(row)
        row["score_reason"] = explain(row)
    return rows
