"""Cadastro local de provedores de IA (para analisar de dentro do app).

Os provedores ficam em ``providers.json`` no diretorio de dados do usuario, com
permissao restrita (0600). Se nao houver provedor cadastrado, o app cai na
configuracao por variaveis de ambiente (``AUCTION_AI_*``).
"""

from __future__ import annotations

import contextlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config as config_module
from . import paths
from .config import AIConfig

#: Tipos de provedor aceitos no cadastro.
KINDS: tuple[str, ...] = ("anthropic", "openai", "gemini", "compatible")

_KIND_LABELS: dict[str, str] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "compatible": "Compativel com OpenAI (base_url)",
}


def kind_label(kind: str) -> str:
    """Rotulo legivel de um tipo de provedor."""
    return _KIND_LABELS.get(kind, kind)


@dataclass(slots=True)
class Provider:
    """Um provedor de IA cadastrado pelo usuario."""

    id: str
    kind: str = "anthropic"
    label: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""

    @property
    def display(self) -> str:
        """Nome amigavel (label ou tipo + modelo) para exibicao."""
        name = self.label.strip() or kind_label(self.kind)
        return f"{name} — {self.model}" if self.model else name


@dataclass(slots=True)
class ProviderBook:
    """Lista de provedores cadastrados e qual deles esta ativo."""

    providers: list[Provider] = field(default_factory=list)
    active: str | None = None

    def get(self, provider_id: str) -> Provider | None:
        """Retorna um provedor pelo id."""
        return next((p for p in self.providers if p.id == provider_id), None)

    def active_provider(self) -> Provider | None:
        """Retorna o provedor ativo, se houver."""
        return self.get(self.active) if self.active else None

    def upsert(self, provider: Provider) -> None:
        """Insere ou atualiza um provedor (e o torna ativo se for o primeiro)."""
        for index, existing in enumerate(self.providers):
            if existing.id == provider.id:
                self.providers[index] = provider
                return
        self.providers.append(provider)
        if self.active is None:
            self.active = provider.id

    def remove(self, provider_id: str) -> None:
        """Remove um provedor; se era o ativo, passa o bastao para outro."""
        self.providers = [p for p in self.providers if p.id != provider_id]
        if self.active == provider_id:
            self.active = self.providers[0].id if self.providers else None

    def set_active(self, provider_id: str) -> None:
        """Define o provedor ativo."""
        self.active = provider_id


def providers_file() -> Path:
    """Caminho do arquivo de provedores."""
    return paths.data_dir() / "providers.json"


def new_id() -> str:
    """Gera um id curto para um novo provedor."""
    return uuid.uuid4().hex[:8]


def load_book() -> ProviderBook:
    """Le o cadastro de provedores (vazio se nao existir ou estiver corrompido)."""
    path = providers_file()
    if not path.exists():
        return ProviderBook()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ProviderBook()
    raw_providers = data.get("providers") if isinstance(data, dict) else None
    providers: list[Provider] = []
    if isinstance(raw_providers, list):
        for raw in raw_providers:
            if not isinstance(raw, dict):
                continue
            providers.append(
                Provider(
                    id=str(raw.get("id") or new_id()),
                    kind=str(raw.get("kind") or "anthropic"),
                    label=str(raw.get("label") or ""),
                    model=str(raw.get("model") or ""),
                    base_url=str(raw.get("base_url") or ""),
                    api_key=str(raw.get("api_key") or ""),
                )
            )
    active = data.get("active") if isinstance(data, dict) else None
    return ProviderBook(providers=providers, active=str(active) if active else None)


def save_book(book: ProviderBook) -> None:
    """Grava o cadastro com permissao restrita (0600)."""
    path = providers_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"active": book.active, "providers": [asdict(p) for p in book.providers]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def to_ai_config(provider: Provider) -> AIConfig:
    """Converte um provedor cadastrado na configuracao usada pelas chamadas."""
    return AIConfig(
        provider=provider.kind,
        model=provider.model,
        api_key=provider.api_key or None,
        base_url=provider.base_url or None,
    )


def resolve_ai_config() -> AIConfig:
    """Configuracao ativa: provedor cadastrado; senao, o ambiente (``AUCTION_AI_*``)."""
    active = load_book().active_provider()
    if active is not None:
        return to_ai_config(active)
    return config_module.load().ai
