from simplified_auction.analyze.render import (
    Block,
    render,
    risco_tag,
    semaforo_tag,
    status_tag,
)

EXEMPLO = {
    "tipo_leilao": "Venda Direta Online",
    "valor_minimo": "R$ 50.074,26",
    "formas_pagamento": ["Exclusivamente à vista"],
    "debitos_mencionados": {"iptu": "não consta", "condominio": "10% do comprador"},
    "ocupacao": {"situacao": "desocupado", "existe_locacao": "indeterminado"},
    "onus_gravames": ["R-1: alienação fiduciária"],
    "prazos": ["30 dias de certidão"],
    "riscos": [
        {"risco": "Certidão desatualizada", "gravidade": "alta", "fundamento": "datada de 2023"}
    ],
    "checklist": [
        {"item": "Vistoria no local", "status": "critico", "observacao": "não feita"},
        {"item": "Matrícula atualizada", "status": "ok"},
    ],
    "semaforo": "vermelho",
    "resumo": "Imóvel com risco alto.",
}


def _tags(blocks):
    return [block.tag for block in blocks if block.tag]


def test_render_traz_secoes_e_semaforo():
    blocks = render(EXEMPLO, meta="provider · manual")
    textos = "\n".join(block.text for block in blocks)
    assert "SEMAFORO: VERMELHO" in textos
    assert "RISCOS" in textos
    assert "CHECKLIST DE DUE DILIGENCE" in textos
    assert "Imóvel com risco alto." in textos
    assert "semaforo_vermelho" in _tags(blocks)
    assert "risco_alta" in _tags(blocks)
    assert "status_critico" in _tags(blocks)
    assert "status_ok" in _tags(blocks)
    assert "provider · manual" in textos


def test_render_aceita_campos_ausentes():
    blocks = render({"semaforo": "verde"})
    assert any(block.tag == "semaforo_verde" for block in blocks)
    assert all(isinstance(block, Block) for block in blocks)


def test_render_texto_bruto_quando_sem_json():
    blocks = render({"raw": "texto solto"})
    assert any(block.tag == "mono" for block in blocks)


def test_render_lida_com_tipos_inesperados():
    blocks = render({"formas_pagamento": "vista", "riscos": "nao e lista"})
    textos = "\n".join(block.text for block in blocks)
    assert "vista" in textos


def test_tags_de_estilo():
    assert semaforo_tag("VERDE") == "semaforo_verde"
    assert semaforo_tag("roxo") == ""
    assert risco_tag("alta") == "risco_alta"
    assert risco_tag(None) == "risco_media"
    assert status_tag("atencao") == "status_atencao"
    assert status_tag("sei la") == "status_nao_consta"
