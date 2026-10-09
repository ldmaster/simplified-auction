import httpx
import respx

from simplified_auction.config import HttpConfig
from simplified_auction.http import HttpClient
from simplified_auction.sources.caixa_csv import LISTA_URL, fetch_lista, parse_lista


def test_parse_lista_conta_e_campos(lista_ac_text):
    props = parse_lista(lista_ac_text)
    assert len(props) == 20
    first = props[0]
    assert first.imovel_id == "10005120"
    assert first.uf == "AC"
    assert first.cidade == "CRUZEIRO DO SUL"
    assert first.preco == 50074.26
    assert first.valor_avaliacao == 150000.0
    assert first.desconto == 66.62
    assert first.tipo == "Terreno"
    assert first.area_terreno == 600.0
    assert first.financiamento is False


def test_parse_lista_tem_financiavel(lista_ac_text):
    props = parse_lista(lista_ac_text)
    assert any(p.financiamento for p in props)


def test_parse_lista_cabecalho_desconhecido():
    assert parse_lista("linha;qualquer;coisa") == []


@respx.mock
def test_fetch_lista(lista_ac_bytes):
    respx.get(LISTA_URL.format(uf="AC")).mock(
        return_value=httpx.Response(200, content=lista_ac_bytes)
    )
    with HttpClient(HttpConfig(min_interval=0.0)) as client:
        props = fetch_lista(client, "AC")
    assert len(props) == 20
