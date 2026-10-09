from simplified_auction.analyze.prompts import build_prompt, prompt_hash
from simplified_auction.analyze.providers import AIError, run_api
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
