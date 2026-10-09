from simplified_auction.gui import state


def test_filtros_persistem(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    state.reset_cache()
    assert state.filters("oportunidades") == {}
    state.save_filters("oportunidades", {"uf": "AC", "text": "RIO"})
    state.reset_cache()
    assert state.filters("oportunidades") == {"uf": "AC", "text": "RIO"}
    assert state.filters("editais") == {}


def test_auto_analyze_persiste(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    state.reset_cache()
    assert state.auto_analyze() is False
    state.set_auto_analyze(True)
    state.reset_cache()
    assert state.auto_analyze() is True


def test_estado_corrompido_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    state.reset_cache()
    (tmp_path / "ui_state.json").write_text("{ nao e json", encoding="utf-8")
    assert state.get("qualquer", "padrao") == "padrao"
