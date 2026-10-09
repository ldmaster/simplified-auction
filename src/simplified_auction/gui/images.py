"""Carregamento de fotos do imovel com Pillow (opcional)."""

from __future__ import annotations

import io
from typing import Any

try:
    from PIL import Image, ImageTk

    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - ambiente sem Pillow
    PILLOW_AVAILABLE = False


def thumbnail(data: bytes, size: tuple[int, int] = (320, 240)) -> Any:
    """Gera uma miniatura Pillow a partir dos bytes de uma imagem.

    Args:
        data: Bytes da imagem.
        size: Tamanho maximo (largura, altura).

    Returns:
        A imagem Pillow redimensionada ou ``None``.
    """
    if not PILLOW_AVAILABLE:
        return None
    try:
        image = Image.open(io.BytesIO(data))
        image.thumbnail(size)
        return image
    except OSError:
        return None


def to_photoimage(image: Any) -> Any:
    """Converte uma imagem Pillow em ``PhotoImage`` do Tk."""
    if image is None or not PILLOW_AVAILABLE:
        return None
    return ImageTk.PhotoImage(image)


def app_icon(size: int = 256) -> Any:
    """Gera o ``PhotoImage`` do icone do app para a janela.

    Args:
        size: Lado do icone em pixels.

    Returns:
        O ``PhotoImage`` ou ``None`` se o Pillow faltar.
    """
    if not PILLOW_AVAILABLE:
        return None
    from ..icon import render_icon

    return to_photoimage(render_icon(size))
