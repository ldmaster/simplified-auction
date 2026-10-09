"""Notificacao no sistema operacional (best-effort, sem dependencia extra).

macOS usa ``osascript``, Linux usa ``notify-send``. Em outros sistemas (ou
quando o comando nao existe) nao faz nada — a GUI ainda mostra a lista.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str) -> bool:
    """Mostra uma notificacao nativa.

    Args:
        title: Titulo da notificacao.
        message: Corpo da notificacao.

    Returns:
        ``True`` se o comando foi disparado.
    """
    try:
        if sys.platform == "darwin" and shutil.which("osascript"):
            script = (
                f'display notification "{_escape(message)}" with title "{_escape(title)}"'
            )
            subprocess.run(["osascript", "-e", script], check=False, timeout=10)
            return True
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", title, message], check=False, timeout=10
            )
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("falha ao notificar: %s", exc)
    return False
