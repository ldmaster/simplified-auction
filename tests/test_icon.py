import pytest

pytest.importorskip("PIL")

from simplified_auction.icon import render_icon


def test_render_icon_tamanho_modo_e_transparencia():
    image = render_icon(64)
    assert image.size == (64, 64)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((32, 40))[3] > 200


def test_render_icon_tamanhos_usados_no_build():
    for size in (16, 32, 256, 512):
        assert render_icon(size).size == (size, size)
