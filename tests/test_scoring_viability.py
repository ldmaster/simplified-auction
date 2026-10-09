from simplified_auction.scoring import opportunity_score, with_score
from simplified_auction.viability import ViabilityInput, compute


def test_score_favorece_desconto_e_financiamento():
    alto = opportunity_score(
        {"desconto": 60.0, "tipo": "Casa", "financiamento": True, "preco": 200000}
    )
    baixo = opportunity_score(
        {"desconto": 10.0, "tipo": "Terreno", "financiamento": False, "preco": 200000}
    )
    assert alto > baixo
    assert 0 <= baixo <= 100 and 0 <= alto <= 100


def test_with_score_anota():
    rows = with_score([{"desconto": 50.0, "tipo": "Casa", "financiamento": False, "preco": 50000}])
    assert "score" in rows[0] and "score_reason" in rows[0]


def test_viability_custo_total_e_margem():
    result = compute(
        ViabilityInput(preco=100000.0, valor_avaliacao=200000.0, valor_mercado=180000.0,
                       comissao_pct=5.0, itbi_pct=3.0, reforma=5000.0)
    )
    assert result.comissao == 5000.0
    assert result.itbi == 3000.0
    assert result.custo_total == 113000.0
    assert result.margem == 67000.0
    assert result.roi_pct is not None and result.roi_pct > 0
