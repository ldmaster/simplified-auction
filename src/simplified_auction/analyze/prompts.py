"""Prompts do checklist juridico para a analise por IA."""

from __future__ import annotations

import hashlib
from typing import Any

from ..models import DUE_DILIGENCE_ITEMS

SYSTEM_PROMPT = (
    "Voce e um advogado imobiliario brasileiro especializado em leiloes da Caixa "
    "Economica Federal (alienacao fiduciaria, Lei 9.514/97, com as alteracoes da "
    "Lei 14.711/2023, e leilao judicial no CPC). Analise o documento com rigor, "
    "aponte riscos concretos e nao invente dados: quando a informacao nao constar, "
    "use 'nao consta'."
)

_JSON_KEYS = """{
  "tipo_leilao": "string",
  "data_leilao": "string",
  "valor_minimo": "string",
  "formas_pagamento": ["string"],
  "debitos_mencionados": {"iptu": "string", "condominio": "string", "outros": "string"},
  "ocupacao": {"situacao": "string", "existe_locacao": "sim|nao|indeterminado"},
  "onus_gravames": ["string"],
  "prazos": ["string"],
  "riscos": [{"risco": "string", "gravidade": "alta|media|baixa", "fundamento": "string"}],
  "checklist": [{"item": "string", "status": "ok|atencao|critico|nao_consta",
                 "observacao": "string"}],
  "semaforo": "verde|amarelo|vermelho",
  "resumo": "string"
}"""


def _fmt(value: Any) -> str:
    return "nao informado" if value in (None, "") else str(value)


def build_prompt(
    imovel: dict[str, Any],
    detail: dict[str, Any] | None,
    document_text: str,
    *,
    max_chars: int = 60_000,
) -> str:
    """Monta o prompt de analise (ficha do imovel + documento + checklist).

    Args:
        imovel: Linha do catalogo.
        detail: Ficha enriquecida (pode ser ``None``).
        document_text: Texto extraido do documento.
        max_chars: Limite de caracteres do documento enviado.

    Returns:
        O prompt completo.
    """
    detail = detail or {}
    checklist = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(DUE_DILIGENCE_ITEMS))
    snippet = document_text[:max_chars]
    header = (
        "DADOS DO IMOVEL (catalogo Caixa):\n"
        f"- id: {_fmt(imovel.get('imovel_id'))}\n"
        f"- cidade/UF: {_fmt(imovel.get('cidade'))}/{_fmt(imovel.get('uf'))}\n"
        f"- bairro: {_fmt(imovel.get('bairro'))}\n"
        f"- tipo: {_fmt(imovel.get('tipo'))}\n"
        f"- modalidade de venda: {_fmt(imovel.get('modalidade'))}\n"
        f"- preco: {_fmt(imovel.get('preco'))}\n"
        f"- valor de avaliacao: {_fmt(imovel.get('valor_avaliacao'))}\n"
        f"- desconto (%): {_fmt(imovel.get('desconto'))}\n"
        f"- descricao: {_fmt(imovel.get('descricao'))}\n"
        f"- matricula: {_fmt(detail.get('matricula'))}\n"
        f"- comarca: {_fmt(detail.get('comarca'))}\n"
        f"- formas de pagamento (ficha): {_fmt(detail.get('formas_pagamento'))}\n"
        f"- regras de despesas (ficha): {_fmt(detail.get('regras_despesas'))}\n"
    )
    body = (
        "\nCHECKLIST DE DUE DILIGENCE A RESPONDER:\n"
        f"{checklist}\n"
        "\nDOCUMENTO (texto extraido):\n"
        "----------------------------------------\n"
        f"{snippet}\n"
        "----------------------------------------\n"
        "\nResponda SOMENTE com um JSON valido no formato abaixo, em portugues:\n"
        f"{_JSON_KEYS}\n"
    )
    return f"{SYSTEM_PROMPT}\n\n{header}{body}"


def prompt_hash(prompt: str) -> str:
    """Hash estavel do prompt (para cache/idempotencia)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
