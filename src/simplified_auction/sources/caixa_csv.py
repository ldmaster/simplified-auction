"""Coleta e parsing da lista oficial de imoveis da Caixa (CSV)."""

from __future__ import annotations

import csv
import io

from .. import CAIXA_BASE
from ..http import HttpClient
from ..models import Property
from ..normalize import ascii_fold, parse_descricao, parse_number

LISTA_URL = CAIXA_BASE + "/listaweb/Lista_imoveis_{uf}.csv"

#: UFs aceitas + o valor especial ``geral`` (todos os estados).
UFS: tuple[str, ...] = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO", "geral",
)

_COLUMNS: tuple[str, ...] = (
    "n_do_imovel",
    "uf",
    "cidade",
    "bairro",
    "endereco",
    "preco",
    "valor_de_avaliacao",
    "desconto",
    "financiamento",
    "descricao",
    "modalidade_de_venda",
    "link_de_acesso",
)


def parse_lista(text: str) -> list[Property]:
    """Parseia o CSV da lista oficial (2 linhas de cabecalho, ``;``).

    Args:
        text: Conteudo do CSV ja decodificado (cp1252).

    Returns:
        Lista de imoveis; vazia se o cabecalho nao for reconhecido.
    """
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    header: list[str] | None = None
    start = 0
    for index, row in enumerate(rows):
        folded = [ascii_fold(cell) for cell in row]
        if "n_do_imovel" in folded:
            header = folded
            start = index + 1
            break
    if header is None:
        return []
    pos = {name: header.index(name) for name in _COLUMNS if name in header}

    def cell(row: list[str], name: str) -> str:
        idx = pos.get(name)
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip()

    properties: list[Property] = []
    for row in rows[start:]:
        if not any(part.strip() for part in row):
            continue
        imovel_id = cell(row, "n_do_imovel")
        if not imovel_id:
            continue
        descricao = cell(row, "descricao")
        extra = parse_descricao(descricao)
        properties.append(
            Property(
                imovel_id=imovel_id,
                uf=cell(row, "uf").upper(),
                cidade=cell(row, "cidade"),
                bairro=cell(row, "bairro"),
                endereco=cell(row, "endereco"),
                descricao=descricao,
                modalidade=cell(row, "modalidade_de_venda"),
                link=cell(row, "link_de_acesso"),
                tipo=extra["tipo"],
                area_total=extra["area_total"],
                area_privativa=extra["area_privativa"],
                area_terreno=extra["area_terreno"],
                quartos=extra["quartos"],
                salas=extra["salas"],
                vagas=extra["vagas"],
                wc=extra["wc"],
                cozinha=extra["cozinha"],
                area_servico=extra["area_servico"],
                preco=parse_number(cell(row, "preco")),
                valor_avaliacao=parse_number(cell(row, "valor_de_avaliacao")),
                desconto=parse_number(cell(row, "desconto")),
                financiamento=ascii_fold(cell(row, "financiamento")) == "sim",
            )
        )
    return properties


def fetch_lista(client: HttpClient, uf: str) -> list[Property]:
    """Baixa e parseia a lista oficial de um estado (ou ``geral``).

    Args:
        client: Cliente HTTP (com throttle/retry).
        uf: Sigla do estado ou ``geral``.

    Returns:
        Os imoveis do estado.
    """
    text = client.get_text(LISTA_URL.format(uf=uf), encoding="cp1252")
    return parse_lista(text)
