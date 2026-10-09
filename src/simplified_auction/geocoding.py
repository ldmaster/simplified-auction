"""Enderecos: texto para mapas e geocodificacao via Nominatim (OpenStreetMap)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from .http import HttpClient, HttpError

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_MAPS_SEARCH = "https://www.google.com/maps/search/"
GOOGLE_MAPS_DIR = "https://www.google.com/maps/dir/"


@dataclass(slots=True)
class GeocodeResult:
    """Coordenadas encontradas e a consulta que funcionou."""

    lat: float
    lon: float
    query: str


def address_line(row: dict[str, Any], detail: dict[str, Any] | None = None) -> str:
    """Monta o endereco completo em uma linha (para o Google Maps)."""
    detail = detail or {}
    parts: list[str] = []
    endereco = detail.get("endereco") or row.get("endereco")
    if endereco:
        parts.append(str(endereco))
    if row.get("bairro"):
        parts.append(str(row["bairro"]))
    cidade = str(row.get("cidade") or "")
    uf = str(row.get("uf") or "")
    if cidade:
        parts.append(f"{cidade} - {uf}" if uf else cidade)
    cep = detail.get("cep")
    if cep:
        parts.append(f"CEP {cep}")
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _street(row: dict[str, Any], detail: dict[str, Any]) -> str:
    endereco = str(detail.get("endereco") or row.get("endereco") or "")
    return endereco.split(",")[0].strip()


def search_candidates(
    row: dict[str, Any], detail: dict[str, Any] | None = None
) -> list[str]:
    """Consultas de geocodificacao, da mais especifica para a mais generica."""
    detail = detail or {}
    cidade = str(row.get("cidade") or "").title()
    uf = str(row.get("uf") or "")
    bairro = str(row.get("bairro") or "").title()
    cep = str(detail.get("cep") or "")
    rua = _street(row, detail).title()
    candidates = [
        address_line(row, detail),
        f"{rua}, {bairro}, {cidade} - {uf}, Brasil" if rua and bairro and cidade else "",
        f"{cep}, {cidade} - {uf}, Brasil" if cep and cidade else "",
        f"{bairro}, {cidade} - {uf}, Brasil" if bairro and cidade else "",
        f"{cidade} - {uf}, Brasil" if cidade else "",
    ]
    unique: list[str] = []
    for query in candidates:
        if query and query not in unique:
            unique.append(query)
    return unique


def google_maps_url(address: str) -> str:
    """URL de busca no Google Maps para um endereco."""
    return f"{GOOGLE_MAPS_SEARCH}?{urlencode({'api': '1', 'query': address})}"


def google_maps_route_url(address: str) -> str:
    """URL de rota (da sua localizacao) no Google Maps."""
    return f"{GOOGLE_MAPS_DIR}?{urlencode({'api': '1', 'destination': address})}"


def _search(client: HttpClient, query: str) -> GeocodeResult | None:
    try:
        response = client.request(
            "GET",
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"Accept": "application/json"},
        )
    except HttpError:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    first = data[0]
    try:
        return GeocodeResult(lat=float(first["lat"]), lon=float(first["lon"]), query=query)
    except (KeyError, TypeError, ValueError):
        return None


def geocode(client: HttpClient, candidates: Sequence[str]) -> GeocodeResult | None:
    """Tenta geocodificar cada consulta ate achar coordenadas.

    Args:
        client: Cliente HTTP (rate-limit respeita a politica do Nominatim).
        candidates: Consultas, da mais especifica para a mais generica.

    Returns:
        O resultado ou ``None``.
    """
    for query in candidates:
        found = _search(client, query)
        if found is not None:
            return found
    return None
