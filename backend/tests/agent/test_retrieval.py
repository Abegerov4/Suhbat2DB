import json
from pathlib import Path

import pytest

from app.agent.examples import ExamplesIndexer, examples_for
from app.agent.retrieval.linker import SchemaLinker, bridges, fk_graph, full_schema
from app.agent.retrieval.sparse import sparse_document, sparse_query, tokenize
from app.agent.retrieval.store import SchemaStore, SearchMode, build_documents
from app.schemas.schema_snapshot import SchemaSnapshot

DEMO = Path(__file__).resolve().parents[1] / "validator" / "demo_schema.json"


@pytest.fixture(scope="module")
def demo() -> SchemaSnapshot:
    snapshot = SchemaSnapshot.model_validate_json(DEMO.read_text(encoding="utf-8"))
    snapshot.datasource_id = "demo"
    return snapshot


def test_tokenize_stems_and_splits_identifiers() -> None:
    tokens = tokenize("Сумма заказов total_amount ORDERS по регионам")
    assert "total" in tokens and "amount" in tokens  # идентификатор разбит по «_»
    assert tokenize("заказов") == tokenize("заказы")  # русская основа
    assert tokenize("orders") == tokenize("order")  # английская основа
    assert "по" not in tokens  # стоп-слово


def test_sparse_vectors() -> None:
    _, values = sparse_document("заказ заказы orders")
    assert sorted(values, reverse=True)[0] == 2.0  # TF: «заказ» дважды
    q_indices, q_values = sparse_query("заказ заказы")
    assert len(q_indices) == 1 and q_values == [1.0]


def test_documents_cover_tables_columns_values(demo: SchemaSnapshot) -> None:
    docs = build_documents(demo)
    kinds = {d.kind for d in docs}
    assert kinds == {"table", "column", "value"}
    values = [d for d in docs if d.kind == "value" and d.table == "regions"]
    assert any(d.value == "Алматинская область" for d in values)


def test_bridges_include_all_shortest_paths(demo: SchemaSnapshot) -> None:
    graph = fk_graph(demo)
    # регион связан с заказами через менеджера (2 шага) — кратчайший путь
    assert bridges(graph, ("public", "regions"), ("public", "orders")) == {("public", "managers")}
    # город — через клиента
    assert bridges(graph, ("public", "cities"), ("public", "orders")) == {("public", "customers")}
    assert bridges(graph, ("public", "orders"), ("public", "fiscal_calendar")) == set()


def test_full_schema_render(demo: SchemaSnapshot) -> None:
    text = full_schema(demo).render()
    assert "TABLE public.orders (" in text
    assert "REFERENCES public.customers(id)" in text
    assert "'Алматинская область'" in text
    assert "Asia/Almaty" in text


def test_examples_match_demo_schema(demo: SchemaSnapshot) -> None:
    assert len(examples_for(demo)) == 20
    other = demo.model_copy(update={"tables": demo.tables[:2]})
    assert examples_for(other) == []


async def test_index_search_and_link(store: SchemaStore, demo: SchemaSnapshot) -> None:
    await ExamplesIndexer(store).index(demo)
    hits = await store.search("demo", "способ оплаты kaspi_qr", 10)
    assert hits and hits[0].doc.table == "payments"

    modes: tuple[SearchMode, ...] = ("dense", "sparse")
    for mode in modes:
        assert await store.search("demo", "оплата", 5, mode)

    linker = SchemaLinker(store, top_tables=3, candidates=30)
    linked = await linker.link("Сумма заказов total_amount по названию региона regions", demo)
    assert {"orders", "regions"} <= set(linked.table_names)
    assert linked.added_for_joins  # промежуточные таблицы для JOIN добавлены

    examples = await store.search_examples("demo", "Сколько всего заказов?", 2)
    assert examples[0].question == "Сколько всего заказов?"
    assert await store.search_examples("demo", "x", 0) == []

    await store.delete("demo")
    assert await store.search("demo", "заказы", 5) == []


def test_examples_are_valid_json() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "agent" / "examples"
    for path in root.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["requires_tables"] and data["examples"]
