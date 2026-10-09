"""Configuracao do app (variaveis de ambiente + defaults sensatos)."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from . import __version__, paths

#: User-Agent padrao. O WAF da Caixa pontua o conjunto de cabecalhos e bloqueia
#: clientes que nao parecem navegador (inclusive UAs com o nome do app); por
#: isso usamos um UA de navegador. Configure ``AUCTION_USER_AGENT`` para mudar.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

#: User-Agent honesto para APIs publicas (a BrasilAPI recusa fingerprint de navegador).
PLAIN_USER_AGENT = (
    f"simplified-auction/{__version__} "
    "(+https://github.com/ldmaster/simplified-auction)"
)


def browser_headers(user_agent: str) -> dict[str, str]:
    """Cabecalhos que imitam um navegador (necessarios para passar pelo WAF).

    Args:
        user_agent: User-Agent a enviar.

    Returns:
        O dicionario de cabecalhos padrao.
    """
    return {
        "User-Agent": user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive",
    }


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Parametros de rede: educacao com o servidor da Caixa."""

    user_agent: str = DEFAULT_USER_AGENT
    timeout: float = 40.0
    min_interval: float = 1.5
    retries: int = 3
    backoff: float = 1.5
    browser: bool = False
    browser_fingerprint: bool = True


def external_http_config(base: HttpConfig) -> HttpConfig:
    """Configuracao para APIs publicas (sem fingerprint de navegador).

    A BrasilAPI responde 403 a cabecalhos de navegador; ja a Caixa exige o
    oposto. Entao cada grupo de fontes usa o cliente adequado.

    Args:
        base: Configuracao base (timeouts e intervalo).

    Returns:
        A configuracao ajustada para APIs abertas.
    """
    return replace(base, user_agent=PLAIN_USER_AGENT, browser_fingerprint=False)


@dataclass(frozen=True, slots=True)
class AIConfig:
    """Parametros da analise de documentos por IA (modo hibrido)."""

    provider: str = "manual"
    model: str = ""
    api_key: str | None = None
    base_url: str | None = None

    @property
    def has_api(self) -> bool:
        """True quando o provedor roda automaticamente (chave ou CLI local)."""
        if self.provider == "manual":
            return False
        if self.provider == "command-code":
            return True
        return bool(self.api_key)


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
