from simplified_auction.sources.external import (
    describe_cep,
    describe_cnpj,
    extract_cnpjs,
    only_digits,
)


def test_only_digits():
    assert only_digits("69980-000") == "69980000"
    assert only_digits("") == ""


def test_extract_cnpjs_sem_repetir():
    texto = "Credor: Caixa (CNPJ 00.360.305/0001-04) e tambem 00360305000104"
    assert extract_cnpjs(texto) == ["00360305000104"]
    assert extract_cnpjs("sem documento") == []


def test_describe_cep():
    data = {
        "cep": "69980000",
        "state": "AC",
        "city": "Cruzeiro do Sul",
        "neighborhood": None,
        "ibge": {"city": "1200203"},
        "location": {"coordinates": {"latitude": "-7.62", "longitude": "-72.67"}},
    }
    rows = dict(describe_cep(data))
    assert rows["Cidade/UF"] == "Cruzeiro do Sul - AC"
    assert rows["Codigo IBGE"] == "1200203"
    assert rows["Coordenadas"] == "-7.62, -72.67"
    assert "Bairro" not in rows


def test_describe_cep_formato_viacep():
    rows = dict(
        describe_cep(
            {"cep": "69980-000", "logradouro": "RUA X", "localidade": "Rio Branco", "uf": "AC"}
        )
    )
    assert rows["Endereco"] == "RUA X"
    assert rows["Cidade/UF"] == "Rio Branco - AC"


def test_describe_cnpj():
    data = {
        "razao_social": "CAIXA ECONOMICA FEDERAL",
        "descricao_situacao_cadastral": "ATIVA",
        "cnae_fiscal_descricao": "Caixas economicas",
        "municipio": "BRASILIA",
        "uf": "DF",
        "capital_social": 1000.0,
    }
    rows = dict(describe_cnpj(data))
    assert rows["Razao social"] == "CAIXA ECONOMICA FEDERAL"
    assert rows["Situacao cadastral"] == "ATIVA"
    assert rows["Capital social"] == "R$ 1.000,00"
