"""Utilitarios de texto compartilhados: tema (claro/escuro) e blocos."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from ..analyze.render import Block
from .theme import is_dark, palette, tag_options


def detect_dark(widget: Any) -> bool:
    """Detecta se o tema do sistema e escuro, pela cor de fundo real do widget."""
    try:
        background = str(widget.cget("background"))
        red, green, blue = widget.winfo_rgb(background)
    except tk.TclError:
        return False
    return is_dark((int(red / 257), int(green / 257), int(blue / 257)))


def style_text(widget: Any) -> None:
    """Aplica ao widget de texto as cores e as tags do tema atual."""
    dark = detect_dark(widget)
    colors = palette(dark)
    widget.configure(foreground=colors["body"], insertbackground=colors["body"])
    for tag, options in tag_options(dark).items():
        widget.tag_configure(tag, **options)


def write_blocks(widget: Any, blocks: list[Block]) -> None:
    """Escreve os blocos no widget de texto, aplicando as tags."""
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    for block in blocks:
        start = widget.index("insert")
        widget.insert("end", f"{block.text}\n")
        if block.tag:
            widget.tag_add(block.tag, start, "insert")
    widget.configure(state="disabled")
    widget.mark_set("insert", "1.0")
    widget.see("1.0")
