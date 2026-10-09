"""Novidades do catalogo: o que apareceu, mudou de preco ou saiu."""

from __future__ import annotations

from typing import Any

#: Rotulos das categorias de novidade.
KIND_LABELS: dict[str, str] = {
    "novo": "Imovel novo",
    "preco": "Queda de preco",
    "saiu": "Saiu do catalogo",
    "documento": "Documento novo",
}


def kind_label(kind: str) -> str:
    """Rotulo legivel de uma categoria de novidade."""
    return KIND_LABELS.get(kind, kind)


#: Singular e plural de cada categoria, para o resumo.
_PLURAL: dict[str, tuple[str, str]] = {
    "novo": ("imovel novo", "imoveis novos"),
    "preco": ("queda de preco", "quedas de preco"),
    "saiu": ("saida do catalogo", "saidas do catalogo"),
    "documento": ("documento novo", "documentos novos"),
}


def counts(items: list[dict[str, Any]]) -> dict[str, int]:
    """Conta as novidades por categoria."""
    result: dict[str, int] = {}
    for item in items:
        kind = str(item.get("kind") or "?")
        result[kind] = result.get(kind, 0) + 1
    return result


def summary(items: list[dict[str, Any]]) -> str:
    """Resumo curto em uma linha (ex.: ``2 imoveis novos, 1 documento novo``)."""
    if not items:
        return "nada novo"
    parts: list[str] = []
    for kind, total in counts(items).items():
        singular, plural = _PLURAL.get(kind, (kind, kind))
        parts.append(f"{total} {singular if total == 1 else plural}")
    return ", ".join(parts)
