"""Analise de documentos do imovel por IA (modo hibrido: API ou manual)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..store import Store
from .extract import extract_text
from .prompts import build_prompt, prompt_hash
from .providers import AIError, run_api
from .result import parse_result, semaforo_of

__all__ = [
    "AIError",
    "PreparedPrompt",
    "build_prompt",
    "extract_text",
    "parse_result",
    "prepare",
    "prompt_hash",
    "run_api",
    "semaforo_of",
    "store_result",
]


@dataclass(slots=True)
class PreparedPrompt:
    """Prompt pronto para envio (ou para colar no modelo web)."""

    prompt: str
    digest: str
    document_id: int | None
    text_length: int


def prepare(
    store: Store,
    imovel_id: str,
    *,
    document_id: int | None = None,
    text: str | None = None,
) -> PreparedPrompt:
    """Monta o prompt de analise a partir da ficha e de um documento.

    Args:
        store: Repositorio.
        imovel_id: Imovel alvo.
        document_id: Documento (PDF ja baixado) a analisar.
        text: Texto ja extraido (alternativa a ``document_id``).

    Returns:
        O prompt e metadados.

    Raises:
        AIError: Se nao houver texto nem documento com PDF baixado.
    """
    imovel = store.get_property(imovel_id) or {"imovel_id": imovel_id}
    detail = store.get_detail(imovel_id)
    if text is None:
        if document_id is None:
            raise AIError("Informe um documento (PDF) ou o texto do documento.")
        document = store.get_document(document_id)
        if document is None or not document.get("local_path"):
            raise AIError("Documento sem PDF baixado; rode 'auction docs fetch' antes.")
        text = extract_text(Path(str(document["local_path"])))
    prompt = build_prompt(imovel, detail, text)
    return PreparedPrompt(
        prompt=prompt,
        digest=prompt_hash(prompt),
        document_id=document_id,
        text_length=len(text),
    )


def store_result(
    store: Store,
    *,
    imovel_id: str,
    document_id: int | None,
    provider: str,
    model: str,
    prompt: str,
    raw: str,
) -> tuple[int, dict[str, object]]:
    """Parseia a resposta da IA e persiste a analise.

    Args:
        store: Repositorio.
        imovel_id: Imovel analisado.
        document_id: Documento analisado (se houver).
        provider: Provedor usado.
        model: Modelo usado.
        prompt: Prompt enviado (para o hash).
        raw: Resposta crua do modelo.

    Returns:
        ``(id_da_analise, resultado_parseado)``.
    """
    result = parse_result(raw)
    analysis_id = store.add_analysis(
        imovel_id=imovel_id,
        document_id=document_id,
        provider=provider,
        model=model,
        prompt_hash=prompt_hash(prompt),
        semaforo=semaforo_of(result),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    return analysis_id, result
