import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any, ClassVar

import asyncpg
import pytest
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.agent.examples import ExamplesIndexer
from app.agent.graph import build_graph
from app.agent.llm import NodeKey
from app.agent.nodes import AgentNodes
from app.agent.prompts import PromptRegistry
from app.agent.retrieval.embeddings import HashEmbedder
from app.agent.retrieval.linker import SchemaLinker
from app.agent.retrieval.store import SchemaStore
from app.agent.state import AgentContext
from app.core.config import get_settings
from app.schemas.schema_snapshot import SchemaSnapshot
from app.services.target_db import introspect

Response = BaseModel | dict[str, Any] | Callable[[list[BaseMessage]], Any]


class FakeLLM:
    """Сценарий ответов по узлам. Последний ответ узла повторяется, если сценарий исчерпан."""

    DEFAULTS: ClassVar[dict[str, list[Response]]] = {
        "guard": [{"decision": "allow", "reason": "вопрос о данных"}],
        "ambiguity": [{"status": "clear", "ambiguities": [], "reason": "однозначно"}],
    }

    def __init__(self, **script: list[Response]) -> None:
        self.script = {**{k: list(v) for k, v in self.DEFAULTS.items()}, **script}
        self.calls: list[tuple[str, list[BaseMessage]]] = []
        self.answer = ["Результат ", "готов."]

    def prompts(self, node: str) -> list[str]:
        return [str(m[-1].content) for n, m in self.calls if n == node]

    async def structured[T: BaseModel](
        self,
        node: NodeKey,
        messages: list[BaseMessage],
        schema: type[T],
        config: RunnableConfig | None = None,
    ) -> T:
        self.calls.append((node, messages))
        queue = self.script[node]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(item) and not isinstance(item, BaseModel):
            item = item(messages)
        return item if isinstance(item, schema) else schema.model_validate(item)

    async def stream_text(
        self, node: NodeKey, messages: list[BaseMessage], config: RunnableConfig | None = None
    ) -> AsyncIterator[str]:
        self.calls.append((node, messages))
        for chunk in self.answer:
            yield chunk

    def model_name(self, node: NodeKey) -> str:
        return "fake"


def sql(text: str) -> dict[str, str]:
    return {"sql": text, "explanation": ""}


GOOD_SQL = (
    "SELECT r.name AS region, sum(o.amount) AS total FROM orders o "
    "JOIN regions r ON r.id = o.region_id WHERE o.status <> 'cancelled' "
    "GROUP BY r.name ORDER BY total DESC"
)


@pytest.fixture
async def qdrant() -> AsyncIterator[AsyncQdrantClient]:
    client = AsyncQdrantClient(location=":memory:")
    yield client
    await client.close()


@pytest.fixture
async def store(qdrant: AsyncQdrantClient) -> SchemaStore:
    s = SchemaStore(qdrant, HashEmbedder())
    await s.ensure_collections()
    return s


@pytest.fixture
async def target_pool(target_urls: dict[str, str]) -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(target_urls["reader"], min_size=1, max_size=2)
    yield pool
    await pool.close()


@pytest.fixture
async def target_snapshot(target_pool: asyncpg.Pool, store: SchemaStore) -> SchemaSnapshot:
    async with target_pool.acquire() as conn:
        snapshot = await introspect(conn, uuid.uuid4())
    await ExamplesIndexer(store).index(snapshot)
    return snapshot


@pytest.fixture
def agent_context(target_snapshot: SchemaSnapshot, target_pool: asyncpg.Pool) -> AgentContext:
    return AgentContext(snapshot=target_snapshot, pool=target_pool)


def make_graph(llm: FakeLLM, store: SchemaStore, **kwargs: Any) -> Any:
    nodes = AgentNodes(
        llm=llm,
        prompts=PromptRegistry(get_settings()),
        linker=SchemaLinker(store, top_tables=3, candidates=20),
        store=store,
        **kwargs,
    )
    return build_graph(nodes, InMemorySaver())


async def run(
    graph: Any, graph_input: Any, context: AgentContext, thread: str = "t1"
) -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    """События custom-потока и значение interrupt (если граф остановился)."""
    events: list[tuple[str, dict[str, Any]]] = []
    interrupted = None
    async for mode, chunk in graph.astream(
        graph_input,
        {"configurable": {"thread_id": thread}},
        context=context,
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom":
            events.append((chunk["type"], chunk["data"]))
        elif "__interrupt__" in chunk:
            interrupted = chunk["__interrupt__"][0].value
    return events, interrupted


def of_type(events: list[tuple[str, dict[str, Any]]], kind: str) -> list[dict[str, Any]]:
    return [d for t, d in events if t == kind]
