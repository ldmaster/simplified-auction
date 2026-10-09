"""Resolve o diretorio de dados do usuario (multi-plataforma)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_VAR = "AUCTION_HOME"
APP_DIR_NAME = "simplified-auction"


def data_dir() -> Path:
    """Retorna o diretorio de dados do app, respeitando a variavel ``AUCTION_HOME``.

    Returns:
        O diretorio de dados (pode nao existir ainda).
    """
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share")))
    return base / APP_DIR_NAME


def ensure_data_dir() -> Path:
    """Garante que o diretorio de dados existe e o retorna."""
    target = data_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def default_db_path() -> Path:
    """Caminho padrao do banco SQLite."""
    return data_dir() / "auction.db"


def documents_dir() -> Path:
    """Diretorio onde os PDFs de editais/matriculas sao guardados."""
    return data_dir() / "documents"
