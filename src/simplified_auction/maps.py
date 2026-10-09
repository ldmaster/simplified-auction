"""URLs de mapa do Google (Static Maps) — puro e testavel.

A Maps Static API devolve uma **imagem**, que o Tk exibe nativamente (o Tk nao
renderiza pagina web, entao a Maps Embed API, que e um iframe, nao serve).
Exige chave de API com billing habilitado no projeto do Google Cloud.
"""

from __future__ import annotations

from urllib.parse import urlencode

STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"

#: Tipos de mapa aceitos.
MAP_TYPES: tuple[str, ...] = ("roadmap", "satellite", "hybrid", "terrain")

#: Tamanho maximo aceito pela API (em scale=1).
MAX_SIZE = 640
DEFAULT_SIZE = (640, 400)


def static_map_url(
    api_key: str,
    lat: float,
    lon: float,
    *,
    zoom: int = 16,
    size: tuple[int, int] = DEFAULT_SIZE,
    maptype: str = "roadmap",
    scale: int = 2,
) -> str:
    """Monta a URL da imagem do Google Maps com um marcador no ponto.

    Args:
        api_key: Chave da API (com Maps Static habilitada).
        lat: Latitude.
        lon: Longitude.
        zoom: Nivel de zoom (1..21).
        size: Tamanho em pixels (maximo 640x640).
        maptype: ``roadmap``, ``satellite``, ``hybrid`` ou ``terrain``.
        scale: 1 ou 2 (2 dobra os pixels, para telas de alta densidade).

    Returns:
        A URL da imagem.
    """
    width = min(max(int(size[0]), 1), MAX_SIZE)
    height = min(max(int(size[1]), 1), MAX_SIZE)
    point = f"{lat:.6f},{lon:.6f}"
    params = {
        "center": point,
        "zoom": str(max(min(int(zoom), 21), 1)),
        "size": f"{width}x{height}",
        "scale": "2" if int(scale) == 2 else "1",
        "maptype": maptype if maptype in MAP_TYPES else "roadmap",
        "markers": f"color:red|{point}",
        "language": "pt-BR",
        "region": "br",
        "key": api_key,
    }
    return f"{STATIC_URL}?{urlencode(params)}"
