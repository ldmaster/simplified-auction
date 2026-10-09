"""Configuracao do app (variaveis de ambiente + defaults sensatos)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import __version__, paths

DEFAULT_USER_AGENT = (
    f"Mozilla/5.0 (compatible; simplified-auction/{__version__}; "
    "+https://github.com/ldmaster/simplified-auction)"
)


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Parametros de rede: educacao com o servidor da Caixa."""

    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 40.0
    min_interval: float = 1.5
    retries: int = 3
    backoff: float = 1.5
    browser: bool = False


@dataclass(frozen=True, slots=True)
class AIConfig:
    """Parametros da analise de documentos por IA (modo hibrido)."""

    provider: str = "manual"
    model: str = ""
    api_key: str | None = None
    base_url: str | None = None

    @property
    def has_api(self) -> bool:
        """True quando ha provedor remoto configurado com chave."""
        return self.provider != "manual" and bool(self.api_key)


@dataclass(frozen=True, slots=True)
class Config:
    """Configuracao agregada do aplicativo."""

    db_path: Path
    http: HttpConfig
    ai: AIConfig


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


def load(db_path: Path | None = None) -> Config:
    """Monta a configuracao a partir do ambiente.

    Args:
        db_path: Caminho de banco explicito; senao usa o padrao do usuario.

    Returns:
        A configuracao carregada.
    """
    http = HttpConfig(
        user_agent=_env("AUCTION_USER_AGENT", DEFAULT_USER_AGENT) or DEFAULT_USER_AGENT,
        timeout=float(_env("AUCTION_TIMEOUT", "40") or "40"),
        min_interval=float(_env("AUCTION_MIN_INTERVAL", "1.5") or "1.5"),
        browser=_env("AUCTION_BROWSER", "") == "1",
    )
    ai = AIConfig(
        provider=(_env("AUCTION_AI_PROVIDER", "manual") or "manual").lower(),
        model=_env("AUCTION_AI_MODEL", "") or "",
        api_key=_env("AUCTION_AI_KEY") or _env("ANTHROPIC_API_KEY") or _env("OPENAI_API_KEY"),
        base_url=_env("AUCTION_AI_BASE_URL"),
    )
    return Config(db_path=db_path or paths.default_db_path(), http=http, ai=ai)
