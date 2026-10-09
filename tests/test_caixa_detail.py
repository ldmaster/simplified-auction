import pytest

from simplified_auction.sources.caixa_detail import ParseError, parse_detail


def test_parse_detail_campos(detalhe_html):
    detail = parse_detail(detalhe_html, "10005120")
    assert detail.tipo == "Terreno"
    assert detail.numero_imovel == "000001000512-0"
    assert detail.matricula == "9740"
    assert detail.comarca == "CRUZEIRO DO SUL-AC"
    assert detail.oficio == "01"
    assert detail.averbacao_leiloes == "Averbado"
    assert detail.valor_avaliacao == 150000.0
    assert detail.valor_minimo == 50074.26
    assert detail.desconto == 66.62
    assert detail.cep == "69980-000"


def test_parse_detail_pagamento_e_doc(detalhe_html):
    detail = parse_detail(detalhe_html, "10005120")
    assert detail.formas_pagamento is not None
    assert "vista" in detail.formas_pagamento.lower()
    assert detail.matricula_url is not None
    assert detail.matricula_url.endswith("/editais/matricula/AC/0000010005120.pdf")
    assert detail.fotos
    assert detail.fotos[0].startswith("https://venda-imoveis.caixa.gov.br/fotos/")


def test_parse_detail_sem_ficha_levanta_erro():
    with pytest.raises(ParseError):
        parse_detail("<html><body>desafio anti-bot</body></html>", "1")
