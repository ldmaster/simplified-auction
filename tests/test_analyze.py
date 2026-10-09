import os
import shutil

import pytest

from simplified_auction.analyze.prompts import build_prompt, prompt_hash
from simplified_auction.analyze.providers import (
    AIError,
    enriched_path,
    find_command_code,
    run_api,
)
from simplified_auction.analyze.result import parse_result, semaforo_of
from simplified_auction.config import AIConfig


def test_build_prompt_inclui_checklist_e_documento():
    prompt = build_prompt(
        {"imovel_id": "1", "cidade": "RIO BRANCO", "uf": "AC", "desconto": 50},
        None,
        "texto do edital com clausula X",
    )
    assert "CHECKLIST DE DUE DILIGENCE" in prompt
    assert "texto do edital com clausula X" in prompt
    assert prompt_hash(prompt) == prompt_hash(prompt)


def test_parse_result_json_cercado():
    raw = 'bla ```json\n{"semaforo": "verde", "resumo": "ok"}\n``` fim'
    result = parse_result(raw)
    assert semaforo_of(result) == "verde"


def test_parse_result_texto_livre():
    assert parse_result("sem json aqui") == {"raw": "sem json aqui"}


def test_semaforo_invalido():
    assert semaforo_of({"semaforo": "roxo"}) is None


def test_run_api_manual_erro():
    config = AIConfig(provider="manual", api_key=None)
    try:
        run_api(config, "prompt")
    except AIError as exc:
        assert "manual" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("esperava AIError")


@pytest.mark.skipif(os.name == "nt", reason="script shell")
def test_run_api_command_code_chama_a_cli(tmp_path):
    script = tmp_path / "cmd"
    script.write_text(
        "#!/bin/sh\ncat > /dev/null\necho '{\"semaforo\": \"verde\"}'\n", encoding="utf-8"
    )
    script.chmod(0o755)
    config = AIConfig(provider="command-code", api_key=None, base_url=str(script))
    assert run_api(config, "prompt", timeout=30).strip() == '{"semaforo": "verde"}'


def test_run_api_command_code_sem_binario():
    config = AIConfig(provider="command-code", api_key=None, base_url="/nao/existe/cmd")
    with pytest.raises(AIError):
        run_api(config, "prompt", timeout=5)


def test_enriched_path_inclui_diretorios_comuns(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    parts = enriched_path().split(os.pathsep)
    assert "/opt/homebrew/bin" in parts
    assert "/usr/local/bin" in parts
    assert parts[0] == "/usr/bin"


@pytest.mark.skipif(shutil.which("cmd") is None, reason="cmd nao instalado")
def test_find_command_code_com_path_minimo(monkeypatch):
    # Simula um app aberto pelo Finder: PATH minimo, sem Homebrew.
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    assert find_command_code() is not None


def test_prepare_junta_varios_documentos(tmp_path, monkeypatch):
    from simplified_auction.analyze import prepare
    from simplified_auction.models import Document
    from simplified_auction.store import Store

    monkeypatch.setattr(
        "simplified_auction.analyze.extract_text", lambda path: f"TEXTO:{path.name}"
    )
    store = Store(":memory:")
    for name in ("matricula.pdf", "edital.pdf"):
        pdf = tmp_path / name
        pdf.write_bytes(b"%PDF-1.4 fake")
        doc_id = store.upsert_document(
            Document(
                tipo="T", uf="AC", mes=0, ano=0, nome=name,
                url=f"https://x/{name}", imovel_id="1",
            )
        )
        store.mark_document_downloaded(doc_id, str(pdf), "sha")

    prepared = prepare(store, "1", document_ids=[1, 2])
    assert prepared.document_ids == [1, 2]
    assert len(prepared.sources) == 2
    assert "===== DOCUMENTO: T - matricula.pdf =====" in prepared.prompt
    assert "TEXTO:edital.pdf" in prepared.prompt


def test_prepare_sem_documento_levanta_erro():
    from simplified_auction.analyze import prepare
    from simplified_auction.store import Store

    with pytest.raises(AIError):
        prepare(Store(":memory:"), "1")


def test_prepare_dividide_a_cota_entre_documentos(tmp_path, monkeypatch):
    from simplified_auction.analyze import prepare
    from simplified_auction.models import Document
    from simplified_auction.store import Store

    monkeypatch.setattr("simplified_auction.analyze.extract_text", lambda path: "X" * 200_000)
    store = Store(":memory:")
    for name in ("a.pdf", "b.pdf"):
        pdf = tmp_path / name
        pdf.write_bytes(b"%PDF")
        doc_id = store.upsert_document(
            Document(
                tipo="T", uf="AC", mes=0, ano=0, nome=name,
                url=f"https://x/{name}", imovel_id="1",
            )
        )
        store.mark_document_downloaded(doc_id, str(pdf), "s")

    prepared = prepare(store, "1", document_ids=[1, 2])
    assert prepared.truncated is True
    assert prepared.prompt.count("===== DOCUMENTO") == 2
    assert prepared.prompt.count("[... truncado em") == 2


def test_store_result_grava_document_ids():
    from simplified_auction.analyze import store_result
    from simplified_auction.store import Store

    store = Store(":memory:")
    store_result(
        store, imovel_id="1", provider="manual", model="", prompt="p",
        raw='{"semaforo": "verde"}', document_ids=[3, 4],
    )
    row = store.analyses_for("1")[0]
    assert row["document_ids"] == "3,4"
    assert row["document_id"] == 3


def test_prepare_so_documento_sem_imovel(tmp_path, monkeypatch):
    from simplified_auction.analyze import prepare
    from simplified_auction.models import Document
    from simplified_auction.store import Store

    monkeypatch.setattr("simplified_auction.analyze.extract_text", lambda path: "TEXTO EDITAL")
    store = Store(":memory:")
    pdf = tmp_path / "e.pdf"
    pdf.write_bytes(b"%PDF")
    doc_id = store.upsert_document(
        Document(tipo="Edital", uf="AC", mes=10, ano=2026, nome="e.pdf", url="https://x/e.pdf")
    )
    store.mark_document_downloaded(doc_id, str(pdf), "s")

    prepared = prepare(store, None, document_ids=[doc_id])
    assert "SEM IMOVEL VINCULADO" in prepared.prompt
    assert "TEXTO EDITAL" in prepared.prompt
    assert prepared.document_ids == [doc_id]


def test_analyses_for_document():
    from simplified_auction.analyze import store_result
    from simplified_auction.store import Store

    store = Store(":memory:")
    store_result(
        store, imovel_id=None, provider="manual", model="", prompt="p",
        raw='{"semaforo": "verde"}', document_ids=[7, 9],
    )
    assert len(store.analyses_for_document(9)) == 1
    assert store.analyses_for_document(99) == []
