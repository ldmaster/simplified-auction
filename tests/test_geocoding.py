from simplified_auction.geocoding import (
    address_line,
    google_maps_route_url,
    google_maps_url,
    search_candidates,
)


def test_address_line_monta_endereco_com_cep():
    row = {"endereco": "RUA X, N. 1", "bairro": "CENTRO", "cidade": "RIO BRANCO", "uf": "AC"}
    detail = {"endereco": "RUA X, N. 1", "cep": "69980-000"}
    line = address_line(row, detail)
    assert "RIO BRANCO - AC" in line
    assert "CEP 69980-000" in line


def test_google_maps_urls():
    assert google_maps_url("Rua X, 1").startswith("https://www.google.com/maps/search/?api=1&query=")
    assert google_maps_route_url("Rua X, 1").startswith(
        "https://www.google.com/maps/dir/?api=1&destination="
    )


def test_search_candidates_do_especifico_ao_generico():
    row = {
        "endereco": "RUA DO PURUS, N. S/N, QD 272",
        "bairro": "BAIRRO COHAB",
        "cidade": "CRUZEIRO DO SUL",
        "uf": "AC",
    }
    candidates = search_candidates(row, {"cep": "69980-000"})
    assert candidates[0].startswith("RUA DO PURUS")
    assert candidates[-1] == "Cruzeiro Do Sul - AC, Brasil"
    assert len(candidates) == len(set(candidates))


def test_search_candidates_vazio_sem_dados():
    assert search_candidates({}, None) == []
