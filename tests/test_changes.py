from simplified_auction.changes import counts, kind_label, summary


def test_counts_e_summary():
    items = [{"kind": "novo"}, {"kind": "novo"}, {"kind": "documento"}]
    assert counts(items) == {"novo": 2, "documento": 1}
    texto = summary(items)
    assert "2" in texto and "1" in texto


def test_summary_vazio():
    assert summary([]) == "nada novo"
    assert counts([]) == {}


def test_kind_label():
    assert kind_label("preco") == "Queda de preco"
    assert kind_label("novo") == "Imovel novo"
    assert kind_label("qualquer") == "qualquer"
