"""Interpretacao tolerante da resposta da IA (JSON dentro de texto)."""

from __future__ import annotations

import json
import re
from typing import Any

_RE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_result(text: str) -> dict[str, Any]:
    """Extrai o objeto JSON da resposta do modelo.

    Aceita JSON puro, cercado por ``` ou embutido em texto.

    Args:
        text: Resposta crua do modelo.

    Returns:
        O dicionario parseado ou ``{"raw": texto}`` se nao houver JSON.
    """
    candidate = text.strip()
    fence = _RE_FENCE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            candidate = candidate[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return {"raw": text}
    return data if isinstance(data, dict) else {"raw": text}


def semaforo_of(result: dict[str, Any]) -> str | None:
    """Le o semaforo (verde/amarelo/vermelho) do resultado, se houver."""
    value = result.get("semaforo")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"verde", "amarelo", "vermelho"}:
            return normalized
    return None
