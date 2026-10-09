from simplified_auction.models import Property
from simplified_auction.store import Store


def make(imovel_id="1", uf="AC", preco=100000.0, desconto=50.0):
    return Property(
        imovel_id=imovel_id,
        uf=uf,
        cidade="RIO BRANCO",
        bairro="CENTRO",
        endereco="RUA X, 1",
        descricao="Casa, 100.00 de área privativa, 2 qto(s).",
        modalidade="Venda Online",
        link="https://x",
        tipo="Casa",
        preco=preco,
        valor_avaliacao=200000.0,
        desconto=desconto,
    )


def test_upsert_novo_e_idempotente():
    store = Store(":memory:")
    r1 = store.upsert_properties([make()], snapshot_date="2026-01-01")
    assert r1.new == ["1"]
    r2 = store.upsert_properties([make()], snapshot_date="2026-01-02")
    assert r2.new == []
    assert r2.unchanged == 1
    assert store.counts()["properties"] == 1


def test_queda_de_preco_e_desativacao():
    store = Store(":memory:")
    store.upsert_properties([make("1"), make("2")], snapshot_date="2026-01-01")
    r = store.upsert_properties(
        [make("1", preco=80000.0, desconto=60.0)], snapshot_date="2026-01-02"
    )
    assert r.changed == ["1"]
    assert r.price_drop == ["1"]
    assert r.deactivated == ["2"]
    inactive = store.get_property("2")
    assert inactive is not None and inactive["active"] == 0
    assert len(store.price_history("1")) == 2


def test_nao_desativa_outra_uf():
    store = Store(":memory:")
    store.upsert_properties([make("1", uf="AC"), make("9", uf="SP")], snapshot_date="2026-01-01")
    store.upsert_properties([make("1", uf="AC")], snapshot_date="2026-01-02")
    other = store.get_property("9")
    assert other is not None and other["active"] == 1


def test_pipeline_checklist_e_tarefas():
    store = Store(":memory:")
    store.upsert_properties([make()])
    store.set_stage("1", "due_diligence")
    store.set_notas("1", "checar matricula")
    pipe = store.get_pipeline("1")
    assert pipe["stage"] == "due_diligence"
    assert pipe["notas"] == "checar matricula"

    store.set_checklist_item("1", "Vistoria no local", "ok", "foto feita")
    items = store.get_checklist("1")
    assert len(items) == 14
    assert next(i for i in items if i["item"] == "Vistoria no local")["status"] == "ok"

    task_id = store.add_task("1", "prazo_leilao", "2026-11-01")
    assert store.list_tasks("1")[0]["id"] == task_id
    store.set_task_status(task_id, "concluido")
    assert store.list_tasks("1") == []


def test_list_properties_filtros():
    store = Store(":memory:")
    store.upsert_properties(
        [make("1", desconto=70.0), make("2", desconto=20.0)], snapshot_date="2026-01-01"
    )
    rows = store.list_properties(min_desconto=40)
    assert [r["imovel_id"] for r in rows] == ["1"]
    assert store.list_properties(text="CENTRO")
    assert store.list_properties(text="inexistente") == []


def test_documentos_e_analises():
    from simplified_auction.models import Document

    store = Store(":memory:")
    doc = Document(tipo="Edital", uf="AC", mes=10, ano=2026, nome="E.PDF", url="https://x/E.PDF")
    doc_id = store.upsert_document(doc)
    assert store.upsert_document(doc) == doc_id
    store.mark_document_downloaded(doc_id, "/tmp/E.PDF", "abc")
    stored = store.get_document(doc_id)
    assert stored is not None and stored["sha256"] == "abc"

    analysis_id = store.add_analysis(
        imovel_id="1", document_id=doc_id, provider="manual", model="",
        prompt_hash="h", semaforo="verde", result_json="{}",
    )
    assert store.analyses_for("1")[0]["id"] == analysis_id
