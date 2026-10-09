from simplified_auction.analyze.compare import compare, comparison_prompt, to_blocks

A = {
    "semaforo": "vermelho",
    "resumo": "Risco alto na cadeia dominial.",
    "tipo_leilao": "Venda Online",
    "valor_minimo": "R$ 50.000,00",
    "formas_pagamento": ["a vista"],
    "riscos": [
        {"risco": "Certidao desatualizada", "gravidade": "alta"},
        {"risco": "Ocupacao incerta", "gravidade": "baixa"},
    ],
    "checklist": [
        {"item": "Vistoria", "status": "critico"},
        {"item": "Matricula", "status": "ok"},
    ],
}

B = {
    "semaforo": "verde",
    "resumo": "Sem riscos relevantes.",
    "tipo_leilao": "Venda Online",
    "valor_minimo": "R$ 120.000,00",
    "formas_pagamento": ["a vista"],
    "riscos": [{"risco": "Ocupacao incerta", "gravidade": "baixa"}],
    "checklist": [
        {"item": "Vistoria", "status": "ok"},
        {"item": "Matricula", "status": "ok"},
    ],
}


def test_compare_aponta_diferencas():
    resultado = compare(["A", "B"], [A, B])
    assert resultado.semaforos == ["vermelho", "verde"]
    assert resultado.melhor() == 1
    valor = next(row for row in resultado.rows if row.label == "Valor minimo")
    assert valor.different is True
    tipo = next(row for row in resultado.rows if row.label == "Tipo de leilao")
    assert tipo.different is False


def test_compare_riscos_exclusivos_e_comuns():
    resultado = compare(["A", "B"], [A, B])
    assert [texto for texto, _ in resultado.riscos_so["A"]] == ["Certidao desatualizada"]
    assert "B" not in resultado.riscos_so
    assert resultado.riscos_comuns == ["Ocupacao incerta"]


def test_compare_checklist_divergente():
    resultado = compare(["A", "B"], [A, B])
    divergentes = {row.label for row in resultado.checklist_divergentes}
    assert "Vistoria" in divergentes
    assert "Matricula" not in divergentes


def test_to_blocks_traz_o_porque():
    blocks = to_blocks(compare(["A", "B"], [A, B]))
    texto = "\n".join(block.text for block in blocks)
    assert "COMPARACAO DE 2 ANALISES" in texto
    assert "POR QUE" in texto
    assert "Certidao desatualizada" in texto
    assert "Risco alto na cadeia dominial." in texto
    assert any(block.tag == "diff" for block in blocks)


def test_prompt_inclui_as_analises():
    prompt = comparison_prompt(compare(["A", "B"], [A, B]), [A, B])
    assert "=== ANALISE: A ===" in prompt
    assert "=== ANALISE: B ===" in prompt


def test_compare_sem_riscos_nao_quebra():
    resultado = compare(["X", "Y"], [{}, {}])
    assert resultado.riscos_so == {}
    assert resultado.riscos_comuns == []
    assert resultado.melhor() is None
