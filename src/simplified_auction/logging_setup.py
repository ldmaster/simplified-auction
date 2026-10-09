"""Configuracao de logging do app (arquivo no diretorio de dados + stderr)."""

from __future__ import annotations

import logging

from . import paths

_CONFIGURED = False


def setup(level: int = logging.INFO) -> None:
    """Configura o logging uma unica vez.

    Args:
        level: Nivel minimo do logger raiz.
    """
    global _CONFIGURED

    # Bibliotecas ruidosas: avisos de fonte do pypdf nao interessam ao usuario.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    if _CONFIGURED:
        return
    root = logging.getLogger()
    root.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(stream)

    try:
        path = paths.ensure_data_dir() / "auction.log"
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
    except OSError:
        pass

    _CONFIGURED = True
