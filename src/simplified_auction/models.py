"""Modelos de dominio (dataclasses imutaveis) e constantes do CRM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Property:
    """Imovel do catalogo da Caixa (base: lista oficial em CSV)."""

    imovel_id: str
    uf: str
    cidade: str
    bairro: str
    endereco: str
    descricao: str
    modalidade: str
    link: str
    tipo: str | None = None
    area_total: float | None = None
    area_privativa: float | None = None
    area_terreno: float | None = None
    quartos: int | None = None
    salas: int | None = None
    vagas: int | None = None
    wc: int | None = None
    cozinha: bool = False
    area_servico: bool = False
    preco: float | None = None
    valor_avaliacao: float | None = None
    desconto: float | None = None
    financiamento: bool = False


@dataclass(frozen=True, slots=True)
class Detail:
    """Dados enriquecidos da pagina de detalhe do imovel."""

    imovel_id: str
    fetched_at: str
    tipo: str | None = None
    situacao: str | None = None
    numero_imovel: str | None = None
    matricula: str | None = None
    comarca: str | None = None
    oficio: str | None = None
    inscricao_imobiliaria: str | None = None
    averbacao_leiloes: str | None = None
    valor_avaliacao: float | None = None
    valor_minimo: float | None = None
    desconto: float | None = None
    endereco: str | None = None
    cep: str | None = None
    formas_pagamento: str | None = None
    regras_despesas: str | None = None
    matricula_url: str | None = None
    fotos: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Document:
    """Documento legal publicado pela Caixa (edital, aviso, contrato, matricula)."""

    tipo: str
    uf: str
    mes: int
    ano: int
    nome: str
    url: str
    imovel_id: str | None = None


#: Estagios do pipeline de arrematacao.
STAGES: tuple[str, ...] = (
    "novo",
    "triagem",
    "due_diligence",
    "negociacao",
    "proposta",
    "arrematado",
    "perdido",
    "descartado",
)

#: Rotulos legiveis dos estagios.
STAGE_LABELS: dict[str, str] = {
    "novo": "Novo",
    "triagem": "Triagem",
    "due_diligence": "Due diligence",
    "negociacao": "Negociacao",
    "proposta": "Proposta",
    "arrematado": "Arrematado",
    "perdido": "Perdido",
    "descartado": "Descartado",
}

#: Checklist de due diligence (lente de advogado imobiliario).
DUE_DILIGENCE_ITEMS: tuple[str, ...] = (
    "Matricula atualizada e onus reais",
    "Certidao de onus e gravames (CRI)",
    "Acoes judiciais / reipersecutorias",
    "IPTU / dívida ativa / ITR",
    "Debitos de condominio (propter rem)",
    "Contas de agua / luz / taxas",
    "Situacao de ocupacao (quem ocupa)",
    "Existe locacao? contrato averbado?",
    "Regularidade da construcao (habite-se)",
    "Regras de despesas do edital (quem paga)",
    "Prazo e forma de pagamento",
    "Comissao do leiloeiro",
    "Risco de anulacao / purgacao pelo devedor",
    "Vistoria no local",
)

#: Tipos de documento (codigo -> rotulo) da busca de publicacoes da Caixa.
DOCUMENT_TYPES: dict[str, str] = {
    "1": "Aviso de Anulacao de Item",
    "2": "Aviso de Dispensa de Licitacao",
    "3": "Aviso de Homologacao de Licitacao",
    "4": "Aviso de Revogacao de Licitacao",
    "5": "Aviso de Venda",
    "6": "Extrato de Contrato",
    "7": "Extrato de Dispensa de Licitacao",
    "8": "Edital de Publicacao do 1o e 2o Leilao SFI",
    "9": "Edital de Publicacao do Leilao SFI - Edital Unico",
}

#: Modalidades de venda do catalogo (codigo -> rotulo).
MODALITIES: dict[str, str] = {
    "14": "Leilao SFI - Edital Unico",
    "30": "Exercicio de Direito de Preferencia",
    "21": "Licitacao Aberta",
    "33": "Venda Online",
    "34": "Compra Direta (Venda Direta Online)",
}
