from simplified_auction.normalize import (
    ascii_fold,
    parse_cep,
    parse_descricao,
    parse_number,
)


def test_parse_number_formatos():
    assert parse_number("50.074,26") == 50074.26
    assert parse_number("R$ 150.000,00") == 150000.0
    assert parse_number("66.62") == 66.62
    assert parse_number("0.00") == 0.0
    assert parse_number("") is None
    assert parse_number(None) is None


def test_parse_descricao_casa():
    extra = parse_descricao(
        "Casa, 111.70 de área total, 111.70 de área privativa, 300.00 de área "
        "do terreno,  1 qto(s), a.serv, WC, 1 sala(s), cozinha, 2 vaga(s) de garagem."
    )
    assert extra["tipo"] == "Casa"
    assert extra["area_privativa"] == 111.7
    assert extra["area_terreno"] == 300.0
    assert extra["quartos"] == 1
    assert extra["salas"] == 1
    assert extra["vagas"] == 2
    assert extra["wc"] == 1
    assert extra["cozinha"] is True
    assert extra["area_servico"] is True


def test_parse_descricao_terreno():
    extra = parse_descricao("Terreno, 0.00 de área total, 600.00 de área do terreno.")
    assert extra["tipo"] == "Terreno"
    assert extra["area_terreno"] == 600.0
    assert extra["quartos"] is None


def test_parse_cep():
    assert parse_cep("... CEP: 69980-000, CRUZEIRO DO SUL") == "69980-000"
    assert parse_cep("CEP 69980000") == "69980-000"
    assert parse_cep("sem cep") is None


def test_ascii_fold():
    assert ascii_fold("N° do imóvel") == "n_do_imovel"
    assert ascii_fold("Modalidade de venda") == "modalidade_de_venda"
