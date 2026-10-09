from simplified_auction.gui.theme import is_dark, palette, semaforo_colors, tag_options


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return 0.299 * red + 0.587 * green + 0.114 * blue


def test_is_dark():
    assert is_dark((255, 255, 255)) is False
    assert is_dark((240, 240, 240)) is False
    assert is_dark((0, 0, 0)) is True
    assert is_dark((30, 30, 30)) is True


def test_modo_escuro_usa_cores_mais_claras():
    claro = palette(False)
    escuro = palette(True)
    for chave in ("body", "h1", "h2", "muted", "mono", "risco_alta", "status_ok"):
        assert _luminance(escuro[chave]) > _luminance(claro[chave])


def test_tag_options_cobre_as_tags_usadas():
    esperadas = (
        "h1", "h2", "bullet", "muted", "mono",
        "risco_alta", "risco_media", "risco_baixa",
        "status_ok", "status_atencao", "status_critico", "status_nao_consta",
        "semaforo_verde", "semaforo_amarelo", "semaforo_vermelho",
    )
    for dark in (False, True):
        opcoes = tag_options(dark)
        for tag in esperadas:
            assert tag in opcoes


def test_semaforo_colors():
    cores = semaforo_colors()
    assert set(cores) == {"verde", "amarelo", "vermelho"}
