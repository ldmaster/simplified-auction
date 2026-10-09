import os
import stat

from simplified_auction import providers
from simplified_auction.providers import (
    Provider,
    ProviderBook,
    load_book,
    resolve_ai_config,
    save_book,
    to_ai_config,
)


def test_book_upsert_e_ativo(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    book = ProviderBook()
    book.upsert(Provider(id="a", kind="anthropic", model="m", api_key="k"))
    assert book.active == "a"
    book.upsert(Provider(id="b", kind="openai", api_key="k2"))
    assert book.active == "a"
    book.set_active("b")
    save_book(book)
    loaded = load_book()
    assert loaded.active == "b"
    assert len(loaded.providers) == 2
    assert loaded.get("a") is not None


def test_remove_reassina_ativo(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    book = ProviderBook(
        providers=[Provider(id="a", kind="openai"), Provider(id="b", kind="openai")],
        active="a",
    )
    book.remove("a")
    assert book.active == "b"
    book.remove("b")
    assert book.active is None


def test_to_ai_config():
    config = to_ai_config(Provider(id="x", kind="gemini", model="gemini-1.5-flash"))
    assert config.provider == "gemini"
    assert config.api_key is None
    assert config.has_api is False


def test_load_book_ignora_arquivo_corrompido(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    (tmp_path / "providers.json").write_text("{ nao e json", encoding="utf-8")
    assert load_book().providers == []


def test_resolve_usa_provedor_ativo(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    for var in ("AUCTION_AI_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    book = ProviderBook(
        providers=[Provider(id="a", kind="anthropic", model="m", api_key="k")], active="a"
    )
    save_book(book)
    config = resolve_ai_config()
    assert config.provider == "anthropic"
    assert config.api_key == "k"
    assert config.has_api


def test_resolve_cai_no_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    monkeypatch.setenv("AUCTION_AI_PROVIDER", "openai")
    monkeypatch.setenv("AUCTION_AI_KEY", "envkey")
    config = resolve_ai_config()
    assert config.provider == "openai"
    assert config.api_key == "envkey"


def test_arquivo_tem_permissao_restrita(tmp_path, monkeypatch):
    monkeypatch.setenv("AUCTION_HOME", str(tmp_path))
    save_book(ProviderBook(providers=[Provider(id="a", api_key="segredo")], active="a"))
    path = providers.providers_file()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
