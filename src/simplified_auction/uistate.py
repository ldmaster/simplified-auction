"""Estado leve da interface (filtros e preferencias) em ``ui_state.json``."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from . import paths

_FILE_NAME = "ui_state.json"
_cache: dict[str, Any] | None = None


def state_path() -> Path:
    """Caminho do arquivo de estado da interface."""
    return paths.data_dir() / _FILE_NAME


def reset_cache() -> None:
    """Descarta o cache em memoria (util em testes)."""
    global _cache
    _cache = None


def load() -> dict[str, Any]:
    """Carrega o estado (vazio se nao existir ou estiver corrompido)."""
    global _cache
    if _cache is not None:
        return _cache
    data: dict[str, Any] = {}
    path = state_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, json.JSONDecodeError):
            data = {}
    _cache = data
    return _cache


def save() -> None:
    """Grava o estado atual (silencioso se o diretorio nao for gravavel)."""
    if _cache is None:
        return
    path = state_path()
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        # Pode conter a chave do Google Maps: restringe a leitura ao dono.
        with contextlib.suppress(OSError):
            path.chmod(0o600)


def get(key: str, default: Any = None) -> Any:
    """Le uma chave do estado."""
    return load().get(key, default)


def put(key: str, value: Any) -> None:
    """Grava uma chave do estado (persistindo em disco)."""
    load()[key] = value
    save()


def filters(name: str) -> dict[str, Any]:
    """Le os filtros salvos de uma tela."""
    all_filters = load().get("filters")
    if isinstance(all_filters, dict) and isinstance(all_filters.get(name), dict):
        result: dict[str, Any] = all_filters[name]
        return result
    return {}


def save_filters(name: str, values: dict[str, Any]) -> None:
    """Salva os filtros de uma tela."""
    all_filters = load().get("filters")
    if not isinstance(all_filters, dict):
        all_filters = {}
    all_filters[name] = values
    load()["filters"] = all_filters
    save()


def auto_analyze() -> bool:
    """Preferencia: rodar a analise de IA com um clique (sem abrir o dialogo)."""
    return bool(load().get("auto_analyze", False))


def set_auto_analyze(value: bool) -> None:
    """Grava a preferencia de analise automatica."""
    put("auto_analyze", bool(value))


def last_check_at() -> str | None:
    """Momento da ultima verificacao de novidades (ISO) ou ``None``."""
    value = load().get("last_check_at")
    return str(value) if value else None


def set_last_check_at(value: str) -> None:
    """Grava o momento da ultima verificacao de novidades."""
    put("last_check_at", value)


def google_maps_key() -> str:
    """Chave da API do Google Maps (vazia se nao configurada)."""
    return str(load().get("google_maps_key") or "")


def set_google_maps_key(value: str) -> None:
    """Grava a chave da API do Google Maps."""
    put("google_maps_key", value.strip())


def map_type() -> str:
    """Tipo de mapa escolhido (roadmap/satellite/hybrid/terrain)."""
    return str(load().get("map_type") or "roadmap")


def set_map_type(value: str) -> None:
    """Grava o tipo de mapa escolhido."""
    put("map_type", value)
