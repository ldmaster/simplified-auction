from pathlib import Path

from simplified_auction.sources.caixa_docs import _parse_listing, matricula_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_matricula_url_deriva_do_id():
    url = matricula_url("ac", "10005120")
    assert url == "https://venda-imoveis.caixa.gov.br/editais/matricula/AC/0000010005120.pdf"


def test_matricula_url_id_ja_com_13_digitos():
    assert matricula_url("SP", "1444420699441").endswith("/matricula/SP/1444420699441.pdf")


def test_parse_listing_extrai_editais(docs_lista_html):
    documents = _parse_listing(docs_lista_html, uf="AC", mes=10, ano=2026)
    assert len(documents) == 3
    first = documents[0]
    assert first.nome == "EL00500226CPARE.PDF"
    assert first.url == (
        "https://venda-imoveis.caixa.gov.br/editais/EL00500226CPARE.PDF"
    )
    assert first.tipo.startswith("Edital de Publica")
    assert first.uf == "AC" and first.mes == 10 and first.ano == 2026
