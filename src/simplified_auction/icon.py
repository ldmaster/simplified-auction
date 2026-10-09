"""Desenho do icone do app (usado na janela e nos binarios).

Um "casa + lupa" sobre um selo em degrade: significa "procurar imoveis".
"""

from __future__ import annotations

from typing import Any

#: Paleta do icone.
NAVY = (13, 40, 71)
TEAL = (16, 158, 155)
DEEP = (7, 22, 42)
AMBER = (244, 165, 41)
WHITE = (255, 255, 255)

_RADIUS = 0.225


def _blend(top: tuple[int, int, int], bottom: tuple[int, int, int], steps: int) -> Any:
    from PIL import Image

    strip = Image.new("RGB", (1, steps))
    for y in range(steps):
        t = y / max(steps - 1, 1)
        strip.putpixel(
            (0, y),
            (
                int(top[0] + (bottom[0] - top[0]) * t),
                int(top[1] + (bottom[1] - top[1]) * t),
                int(top[2] + (bottom[2] - top[2]) * t),
            ),
        )
    return strip


def _ring(draw: Any, center: tuple[float, float], radius: float, width: float, color: Any) -> None:
    cx, cy = center
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], outline=color, width=int(width)
    )


def _line(
    draw: Any, start: tuple[float, float], end: tuple[float, float], width: float, color: Any
) -> None:
    draw.line([start, end], fill=color, width=int(width))
    half = width / 2
    for x, y in (start, end):
        draw.ellipse([x - half, y - half, x + half, y + half], fill=color)


def render_icon(size: int = 512) -> Any:
    """Renderiza o icone do app como imagem RGBA.

    Args:
        size: Lado final em pixels.

    Returns:
        Uma imagem Pillow (RGBA) de ``size`` x ``size``.
    """
    from PIL import Image, ImageDraw

    ss = 4
    side = size * ss
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))

    gradient = _blend(NAVY, TEAL, side).resize((side, side))
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, side - 1, side - 1], radius=int(side * _RADIUS), fill=255
    )
    canvas.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)

    def r(value: float) -> float:
        return value * side

    # Casa (parede + telhado + porta).
    draw.polygon(
        [(r(0.11), r(0.515)), (r(0.365), r(0.245)), (r(0.62), r(0.515))], fill=WHITE
    )
    draw.rounded_rectangle(
        [r(0.175), r(0.50), r(0.555), r(0.795)], radius=r(0.03), fill=WHITE
    )
    draw.rounded_rectangle(
        [r(0.325), r(0.635), r(0.405), r(0.795)], radius=r(0.028), fill=AMBER
    )

    # Lupa (anel + cabo), com um contorno escuro para separar da casa.
    center = (r(0.705), r(0.700))
    outer = r(0.165)
    ring = r(0.058)
    _ring(draw, center, outer, ring + r(0.030), DEEP)
    _ring(draw, center, outer, ring, WHITE)

    start = (r(0.815), r(0.810))
    end = (r(0.930), r(0.925))
    _line(draw, start, end, r(0.090), DEEP)
    _line(draw, start, end, r(0.058), WHITE)

    return canvas.resize((size, size), Image.Resampling.LANCZOS)
