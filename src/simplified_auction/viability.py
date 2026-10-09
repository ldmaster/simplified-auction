"""Calculadora de viabilidade: custo total real e margem."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ViabilityInput:
    """Entradas da calculadora (percentuais em %, valores em R$)."""

    preco: float
    valor_avaliacao: float | None = None
    valor_mercado: float | None = None
    comissao_pct: float = 5.0
    itbi_pct: float = 3.0
    escritura_registro: float = 0.0
    reforma: float = 0.0
    dividas: float = 0.0
    desocupacao: float = 0.0


@dataclass(slots=True)
class ViabilityResult:
    """Saida da calculadora: custo total, margem e ROI."""

    custo_total: float
    comissao: float
    itbi: float
    valor_mercado: float | None
    margem: float | None
    roi_pct: float | None
    desconto_efetivo_pct: float | None


def compute(data: ViabilityInput) -> ViabilityResult:
    """Calcula o custo total de arrematacao e a margem sobre o valor de mercado.

    Args:
        data: Entradas do calculo.

    Returns:
        O resultado detalhado.
    """
    comissao = data.preco * data.comissao_pct / 100.0
    itbi = data.preco * data.itbi_pct / 100.0
    custo_total = (
        data.preco
        + comissao
        + itbi
        + data.escritura_registro
        + data.reforma
        + data.dividas
        + data.desocupacao
    )
    mercado = data.valor_mercado or data.valor_avaliacao
    margem = (mercado - custo_total) if mercado else None
    roi = (margem / custo_total * 100.0) if (margem is not None and custo_total > 0) else None
    desconto = data.valor_avaliacao
    desconto_efetivo = (
        (desconto - custo_total) / desconto * 100.0 if desconto else None
    )
    return ViabilityResult(
        custo_total=round(custo_total, 2),
        comissao=round(comissao, 2),
        itbi=round(itbi, 2),
        valor_mercado=mercado,
        margem=round(margem, 2) if margem is not None else None,
        roi_pct=round(roi, 2) if roi is not None else None,
        desconto_efetivo_pct=round(desconto_efetivo, 2) if desconto_efetivo is not None else None,
    )
