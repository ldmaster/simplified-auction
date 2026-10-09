"""Fixtures compartilhadas dos testes."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def lista_ac_text() -> str:
    return (FIXTURES / "lista_imoveis_AC.csv").read_bytes().decode("cp1252")


@pytest.fixture
def lista_ac_bytes() -> bytes:
    return (FIXTURES / "lista_imoveis_AC.csv").read_bytes()


@pytest.fixture
def detalhe_html() -> str:
    return (FIXTURES / "detalhe_10005120.html").read_text(encoding="utf-8")
