"""Dados externos do imovel a partir de fontes publicas gratuitas (sem chave).

- **CEP** -> endereco normalizado, bairro, municipio/UF, codigo IBGE, fuso e
  coordenadas (BrasilAPI; ViaCEP como reserva).
- **CNPJ** -> razao social, situacao cadastral, atividade, capital social
  (BrasilAPI), util para os CNPJs que aparecem na matricula (credor/devedor).

Outras fontes existem, mas exigem chave, captcha ou pagamento e por isso nao
sao usadas aqui: onus reais (ONR/registradores), preco de mercado (FipeZap e
portais), IPTU/valor venal (municipal) e areas de risco (CEMADEN/IBGE).
"""

from __future__ import annotations

import re
from typing import Any

from ..http import HttpClient, HttpError

BRASILAPI_CEP = "https://brasilapi.com.br/api/cep/v2/{cep}"
BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
VIACEP = "https://viacep.com.br/ws/{cep}/json/"

_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_JSON = {"Accept": "application/json"}


def only_digits(value: str) -> str:
    """Remove tudo que nao for digito."""
    return re.sub(r"\D", "", value or "")


def extract_cnpjs(text: str) -> list[str]:
    """Extrai CNPJs (somente digitos) de um texto, sem repetir."""
    found: list[str] = []
    for match in _CNPJ.findall(text or ""):
        digits = only_digits(match)
        if len(digits) == 14 and digits not in found:
            found.append(digits)
    return found


def lookup_cep(client: HttpClient, cep: str) -> dict[str, Any] | None:
    """Consulta um CEP (BrasilAPI, com ViaCEP de reserva)."""
    digits = only_digits(cep)
    if len(digits) != 8:
        return None
    try:
        response = client.request(
            "GET", BRASILAPI_CEP.format(cep=digits), headers=_JSON
        )
        data = response.json()
        if isinstance(data, dict):
            return data
    except (HttpError, ValueError):
        pass
    try:
        response = client.request(
            "GET", VIACEP.format(cep=f"{digits[:5]}-{digits[5:]}"), headers=_JSON
        )
        data = response.json()
        if isinstance(data, dict) and not data.get("erro"):
            return data
    except (HttpError, ValueError):
        pass
    return None


def lookup_cnpj(client: HttpClient, cnpj: str) -> dict[str, Any] | None:
    """Consulta um CNPJ na BrasilAPI."""
    digits = only_digits(cnpj)
    if len(digits) != 14:
        return None
    try:
        response = client.request(
            "GET", BRASILAPI_CNPJ.format(cnpj=digits), headers=_JSON
        )
        data = response.json()
    except (HttpError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def describe_cep(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Converte o retorno de CEP em pares (rotulo, valor) legiveis."""
    ibge_raw = data.get("ibge")
    ibge: dict[str, Any] = ibge_raw if isinstance(ibge_raw, dict) else {}
    location_raw = data.get("location")
    location: dict[str, Any] = location_raw if isinstance(location_raw, dict) else {}
    coords_raw = location.get("coordinates")
    coords: dict[str, Any] = coords_raw if isinstance(coords_raw, dict) else {}
    latitude = coords.get("latitude")
    longitude = coords.get("longitude")
    rows = [
        ("CEP", str(data.get("cep") or "")),
        ("Endereco", str(data.get("street") or data.get("logradouro") or "")),
        ("Bairro", str(data.get("neighborhood") or data.get("bairro") or "")),
        (
            "Cidade/UF",
            f"{data.get('city') or data.get('localidade') or ''} - "
            f"{data.get('state') or data.get('uf') or ''}".strip(" -"),
        ),
        ("Codigo IBGE", str(ibge.get("city") or data.get("ibge") or "")),
        ("Fuso horario", str(data.get("timezoneName") or "")),
        ("Coordenadas", f"{latitude}, {longitude}" if latitude and longitude else ""),
    ]
    return [(label, value) for label, value in rows if value]


def _brl(value: float) -> str:
    """Formata um valor em reais no padrao brasileiro."""
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def describe_cnpj(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Converte o retorno de CNPJ em pares (rotulo, valor) legiveis."""
    capital = data.get("capital_social")
    rows = [
        ("Razao social", str(data.get("razao_social") or "")),
        ("Nome fantasia", str(data.get("nome_fantasia") or "")),
        ("Situacao cadastral", str(data.get("descricao_situacao_cadastral") or "")),
        ("Atividade principal", str(data.get("cnae_fiscal_descricao") or "")),
        (
            "Municipio/UF",
            f"{data.get('municipio') or ''} - {data.get('uf') or ''}".strip(" -"),
        ),
        ("Aberta em", str(data.get("data_inicio_atividade") or "")),
        ("Capital social", _brl(capital) if isinstance(capital, (int, float)) else ""),
    ]
    return [(label, value) for label, value in rows if value]
