from simplified_auction.sources.caixa_docs import matricula_url


def test_matricula_url_deriva_do_id():
    url = matricula_url("ac", "10005120")
    assert url == "https://venda-imoveis.caixa.gov.br/editais/matricula/AC/0000010005120.pdf"


def test_matricula_url_id_ja_com_13_digitos():
    assert matricula_url("SP", "1444420699441").endswith("/matricula/SP/1444420699441.pdf")
