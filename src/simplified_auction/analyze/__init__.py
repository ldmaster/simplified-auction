"""Analise de documentos do imovel por IA (modo hibrido: API ou manual)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..store import Store
from .extract import extract_text
from .prompts import MAX_DOC_CHARS, build_prompt, prompt_hash
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
    document_ids: list[int] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    text_length: int = 0
    truncated: bool = False


def _combine(store: Store, document_ids: Sequence[int], budget: int) -> tuple[str, list[str], bool]:
    """Junta o texto de varios documentos, com cabecalho e cota por documento.

    Args:
        store: Repositorio.
        document_ids: Ids dos documentos.
        budget: Maximo de caracteres por documento (para nenhum dominar o prompt).

    Returns:
        ``(texto_combinado, rotulos, truncado)``.
    """
    blocks: list[str] = []
    names: list[str] = []
    truncated = False
    for value in document_ids:
        document = store.get_document(int(value))
        if document is None or not document.get("local_path"):
            raise AIError(f"Documento {value} sem PDF baixado; baixe-o antes de analisar.")
        text = extract_text(Path(str(document["local_path"])))
        if len(text) > budget:
            text = f"{text[:budget]}\n[... truncado em {budget} caracteres ...]"
            truncated = True
        label = f"{document.get('tipo') or 'Documento'} - {document.get('nome')}"
        names.append(label)
        blocks.append(f"===== DOCUMENTO: {label} =====\n{text}".strip())
    return "\n\n".join(blocks), names, truncated


def prepare(
    store: Store,
    imovel_id: str | None = None,
    *,
    document_id: int | None = None,
    document_ids: Sequence[int] | None = None,
    text: str | None = None,
) -> PreparedPrompt:
    """Monta o prompt de analise a partir da ficha e dos documentos.

    Args:
        store: Repositorio.
        imovel_id: Imovel alvo (``None`` para analisar so o documento/edital).
        document_id: Um documento (compatibilidade; equivale a ``document_ids``).
        document_ids: Varios documentos (ex.: matricula + editais).
        text: Texto ja extraido (alternativa aos documentos).

    Returns:
        O prompt e metadados (inclusive quais documentos entraram).

    Raises:
        AIError: Se nao houver texto nem documento com PDF baixado.
    """
    ids: list[int] = []
    if document_ids:
        ids = [int(value) for value in document_ids]
    elif document_id is not None:
        ids = [int(document_id)]

    names: list[str] = []
    truncated = False
    if text is None:
        if not ids:
            raise AIError("Selecione ao menos um documento (PDF baixado) ou informe o texto.")
        # Reserva uma folga por documento (cabecalho + marcador de truncagem)
        # para que o total nao estoure o limite e o ultimo documento seja cortado.
        budget = max(MAX_DOC_CHARS // len(ids) - 500, 5_000)
        text, names, truncated = _combine(store, ids, budget)

    imovel = (store.get_property(imovel_id) or {"imovel_id": imovel_id}) if imovel_id else {}
    detail = store.get_detail(imovel_id) if imovel_id else None
    prompt = build_prompt(imovel, detail, text)
    return PreparedPrompt(
        prompt=prompt,
        digest=prompt_hash(prompt),
        document_ids=ids,
        sources=names,
        text_length=len(text),
        truncated=truncated or len(text) > MAX_DOC_CHARS,
    )


def store_result(
    store: Store,
    *,
    imovel_id: str | None,
    provider: str,
    model: str,
    prompt: str,
    raw: str,
    document_id: int | None = None,
    document_ids: Sequence[int] | None = None,
) -> tuple[int, dict[str, object]]:
    """Parseia a resposta da IA e persiste a analise.

    Args:
        store: Repositorio.
        imovel_id: Imovel analisado.
        provider: Provedor usado.
        model: Modelo usado.
        prompt: Prompt enviado (para o hash).
        raw: Resposta crua do modelo.
        document_id: Documento principal (compatibilidade).
        document_ids: Documentos considerados.

    Returns:
        ``(id_da_analise, resultado_parseado)``.
    """
    ids = [int(value) for value in (document_ids or ([document_id] if document_id else []))]
    result = parse_result(raw)
    analysis_id = store.add_analysis(
        imovel_id=imovel_id,
        document_id=ids[0] if ids else None,
        document_ids=ids,
        provider=provider,
        model=model,
        prompt_hash=prompt_hash(prompt),
        semaforo=semaforo_of(result),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    return analysis_id, result
