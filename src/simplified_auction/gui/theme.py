"""Cores que se adaptam ao tema claro/escuro do sistema.

O Tk no macOS segue a aparencia do sistema, entao um texto com cores fixas
(escuras) fica ilegivel no modo escuro. Aqui a paleta e escolhida a partir da
luminancia do fundo real do widget.
"""

from __future__ import annotations

from typing import Any

#: Paleta de texto para cada modo.
_PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "body": "#1a1a1a",
        "h1": "#111111",
        "h2": "#0d2847",
        "muted": "#666666",
        "mono": "#333333",
        "risco_alta": "#c0392b",
        "risco_media": "#a9750a",
        "risco_baixa": "#2c6e9b",
        "status_ok": "#1e9e5a",
        "status_atencao": "#a9750a",
        "status_critico": "#c0392b",
        "status_nao_consta": "#888888",
        "diff": "#a9750a",
    },
    "dark": {
        "body": "#e8e8e8",
        "h1": "#ffffff",
        "h2": "#8ecbff",
        "muted": "#9aa7b4",
        "mono": "#d6d6d6",
        "risco_alta": "#ff7b6b",
        "risco_media": "#f0b429",
        "risco_baixa": "#6fb3e0",
        "status_ok": "#4ecb8b",
        "status_atencao": "#f0b429",
        "status_critico": "#ff7b6b",
        "status_nao_consta": "#9aa7b4",
        "diff": "#f0b429",
    },
}

_SEMAFORO_BG = {
    "semaforo_verde": "#1e9e5a",
    "semaforo_amarelo": "#c98a00",
    "semaforo_vermelho": "#c0392b",
}


def is_dark(rgb: tuple[int, int, int]) -> bool:
    """Diz se uma cor de fundo e escura (luminancia percebida < 128)."""
    red, green, blue = rgb
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return luminance < 128


def palette(dark: bool) -> dict[str, str]:
    """Paleta de texto para o modo informado."""
    return _PALETTES["dark" if dark else "light"]


def tag_options(dark: bool) -> dict[str, dict[str, Any]]:
    """Opcoes das tags de texto do Tk para o modo informado."""
    colors = palette(dark)
    options: dict[str, dict[str, Any]] = {
        "h1": {"font": ("", 15, "bold"), "foreground": colors["h1"]},
        "h2": {
            "font": ("", 11, "bold"),
            "foreground": colors["h2"],
            "spacing1": 10,
            "spacing3": 3,
        },
        "bullet": {"lmargin1": 16, "lmargin2": 30},
        "muted": {"foreground": colors["muted"], "lmargin2": 30},
        "mono": {"font": ("Menlo", 10), "foreground": colors["mono"]},
        "risco_alta": {
            "foreground": colors["risco_alta"],
            "font": ("", 11, "bold"),
            "spacing1": 6,
        },
        "risco_media": {
            "foreground": colors["risco_media"],
            "font": ("", 11, "bold"),
            "spacing1": 6,
        },
        "risco_baixa": {
            "foreground": colors["risco_baixa"],
            "font": ("", 11, "bold"),
            "spacing1": 6,
        },
        "status_ok": {
            "foreground": colors["status_ok"],
            "font": ("", 11, "bold"),
            "spacing1": 4,
        },
        "status_atencao": {
            "foreground": colors["status_atencao"],
            "font": ("", 11, "bold"),
            "spacing1": 4,
        },
        "status_critico": {
            "foreground": colors["status_critico"],
            "font": ("", 11, "bold"),
            "spacing1": 4,
        },
        "status_nao_consta": {
            "foreground": colors["status_nao_consta"],
            "font": ("", 11, "bold"),
            "spacing1": 4,
        },
        "diff": {
            "foreground": colors["diff"],
            "font": ("Menlo", 10, "bold"),
        },
    }
    for tag, background in _SEMAFORO_BG.items():
        options[tag] = {
            "background": background,
            "foreground": "white",
            "font": ("", 12, "bold"),
            "spacing1": 6,
            "spacing3": 6,
        }
    return options


def semaforo_colors() -> dict[str, str]:
    """Cor de fundo do selo de semaforo por valor."""
    return {"verde": "#1e9e5a", "amarelo": "#c98a00", "vermelho": "#c0392b"}
