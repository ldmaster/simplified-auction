from urllib.parse import parse_qs, urlparse

from simplified_auction.maps import MAP_TYPES, MAX_SIZE, static_map_url


def _query(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    assert parsed.netloc == "maps.googleapis.com"
    assert parsed.path == "/maps/api/staticmap"
    return {key: values[0] for key, values in parse_qs(parsed.query).items()}


def test_static_map_url_basico():
    url = static_map_url("MINHA_CHAVE", -7.62759, -72.67756)
    query = _query(url)
    assert query["key"] == "MINHA_CHAVE"
    assert query["center"] == "-7.627590,-72.677560"
    assert query["markers"] == "color:red|-7.627590,-72.677560"
    assert query["size"] == "640x400"
    assert query["maptype"] == "roadmap"
    assert query["language"] == "pt-BR"


def test_static_map_url_respeita_tipo_e_limites():
    url = static_map_url("k", 1.0, 2.0, maptype="satellite", size=(9999, 9999), zoom=99)
    query = _query(url)
    assert query["maptype"] == "satellite"
    assert query["size"] == f"{MAX_SIZE}x{MAX_SIZE}"
    assert query["zoom"] == "21"


def test_static_map_url_tipo_invalido_vira_roadmap():
    assert _query(static_map_url("k", 0.0, 0.0, maptype="qualquer"))["maptype"] == "roadmap"


def test_static_map_url_scale():
    assert _query(static_map_url("k", 0.0, 0.0, scale=2))["scale"] == "2"
    assert _query(static_map_url("k", 0.0, 0.0, scale=1))["scale"] == "1"


def test_map_types():
    assert "satellite" in MAP_TYPES and "hybrid" in MAP_TYPES
