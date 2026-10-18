"""LangGraphAgentRunner через API: SSE, уточнение, продолжение, сохранение ответа."""

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.agent.examples import ExamplesIndexer
from app.agent.langgraph_runner import LangGraphAgentRunner
from app.agent.retrieval.store import SchemaStore
from app.agent.runner import RunContext
from app.api.deps import get_runner
from app.core.config import get_settings
from app.main import app
from app.services import indexer
from app.services.datasources import wait_background
from tests.agent.conftest import GOOD_SQL, FakeLLM, make_graph, sql
from tests.agent.test_graph import AMBIGUOUS
from tests.conftest import parse_sse, requires_db

pytestmark = requires_db


@pytest.fixture
def qdrant_indexer(store: SchemaStore) -> Iterator[None]:
    indexer.set_indexer(ExamplesIndexer(store))
    yield
    indexer.set_indexer(indexer.NoopIndexer())


async def test_runner_through_api(
    client: AsyncClient,
    admin_headers: dict[str, str],
    target_urls: dict[str, str],
    store: SchemaStore,
    qdrant_indexer: None,
) -> None:
    r = await client.post(
        "/api/datasources",
        json={"name": "target", "connection_url": target_urls["reader"]},
        headers=admin_headers,
    )
    datasource_id = r.json()["id"]
    await wait_background()
    assert await store.search(datasource_id, "регионы", 3)  # индекс построен

    llm = FakeLLM(ambiguity=[AMBIGUOUS, {"status": "clear", "ambiguities": [], "reason": "ok"}],
                  generate_sql=[sql(GOOD_SQL)])  # fmt: skip
    runner = LangGraphAgentRunner(make_graph(llm, store), get_settings())
    app.dependency_overrides[get_runner] = lambda: runner

    session = (
        await client.post(
            "/api/sessions", json={"datasource_id": datasource_id}, headers=admin_headers
        )
    ).json()
    url = f"/api/sessions/{session['id']}"
    events = parse_sse(
        (
            await client.post(f"{url}/messages", json={"content": "Продажи"}, headers=admin_headers)
        ).text
    )
    assert [t for t, _ in events][-2:] == ["clarification", "done"]
    assert events[-1][1]["awaiting_clarification"] is True
    assert events[-1][1]["trace_id"] is None  # Langfuse в тестах выключен

    answers = {"answers": [{"ambiguity_id": "a1", "option_id": "a1o1"}]}
    events = parse_sse(
        (await client.post(f"{url}/clarify", json=answers, headers=admin_headers)).text
    )
    kinds = [t for t, _ in events]
    assert {"sql", "validation", "result", "answer"} <= set(kinds) and kinds[-1] == "done"

    messages = (await client.get(f"{url}/messages", headers=admin_headers)).json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["clarification"]["ambiguities"][0]["span"] == "продажи"
    assert messages[3]["result"]["row_count"] == 5
    assert messages[3]["content"] == "Результат готов."


async def test_runner_config_with_trace() -> None:
    import uuid

    runner = LangGraphAgentRunner(graph=None, settings=get_settings())  # type: ignore[arg-type]
    ctx = RunContext(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    config = runner._config(ctx, "0" * 32)
    assert config["configurable"]["thread_id"] == str(ctx.session_id)
    assert config["metadata"]["langfuse_session_id"] == str(ctx.session_id)
    assert isinstance(config["callbacks"], list) and len(config["callbacks"]) == 1
    assert runner._config(ctx, None)["callbacks"] == []
