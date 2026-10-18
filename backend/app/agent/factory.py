"""Сборка агента при старте приложения: Qdrant, эмбеддинги, checkpointer, граф, раннер.

AGENT_MODE=auto: LangGraph-агент, если задан ключ LLM, иначе остаётся заглушка.
"""

from dataclasses import dataclass

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from app.agent.examples import ExamplesIndexer
from app.agent.graph import build_graph
from app.agent.langgraph_runner import LangGraphAgentRunner
from app.agent.llm import LangChainLLM
from app.agent.nodes import AgentNodes
from app.agent.prompts import PromptRegistry
from app.agent.retrieval.embeddings import Embedder, HashEmbedder, OpenAIEmbedder
from app.agent.retrieval.linker import SchemaLinker
from app.agent.retrieval.store import SchemaStore, datasource_filter
from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.models import Datasource, DatasourceStatus
from app.services import datasources, indexer

log = structlog.get_logger()


@dataclass
class AgentServices:
    qdrant: AsyncQdrantClient
    store: SchemaStore
    checkpoint_pool: AsyncConnectionPool
    runner: LangGraphAgentRunner

    async def close(self) -> None:
        await self.checkpoint_pool.close()
        await self.qdrant.close()


def has_llm_key(settings: Settings) -> bool:
    return any(
        k is not None and k.get_secret_value()
        for k in (settings.openai_api_key, settings.anthropic_api_key)
    )


def make_embedder(settings: Settings) -> Embedder:
    if settings.openai_api_key and settings.openai_api_key.get_secret_value():
        return OpenAIEmbedder(settings.embedding_model, settings.openai_api_key.get_secret_value())
    log.warning("embeddings_fallback", reason="нет OPENAI_API_KEY — используются хэш-эмбеддинги")
    return HashEmbedder()


async def create_agent(settings: Settings) -> AgentServices | None:
    if settings.agent_mode == "fake" or (
        settings.agent_mode == "auto" and not has_llm_key(settings)
    ):
        log.warning("agent_fake_mode", reason="нет ключа LLM или AGENT_MODE=fake")
        return None

    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    store = SchemaStore(qdrant, make_embedder(settings))
    await store.ensure_collections()
    indexer.set_indexer(ExamplesIndexer(store))

    pool = AsyncConnectionPool(
        conninfo=settings.app_database_url,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
    await checkpointer.setup()

    nodes = AgentNodes(
        llm=LangChainLLM(settings),
        prompts=PromptRegistry(settings),
        linker=SchemaLinker(
            store, settings.link_top_tables, settings.link_candidates, settings.link_mode
        ),
        store=store,
        few_shot=settings.few_shot_examples,
        max_attempts=settings.agent_max_corrections,
        max_clarification_rounds=settings.max_clarification_rounds,
    )
    runner = LangGraphAgentRunner(build_graph(nodes, checkpointer), settings)
    if settings.langfuse_enabled:
        from langfuse import Langfuse

        assert settings.langfuse_secret_key is not None
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=settings.langfuse_base_url,
        )
    log.info(
        "agent_ready", embeddings=store.embedder.name, llm=nodes.llm.model_name("generate_sql")
    )
    return AgentServices(qdrant, store, pool, runner)


async def reindex_missing(store: SchemaStore) -> None:
    """Источники, проиндексированные до появления Qdrant-индекса, индексируются заново."""
    async with get_sessionmaker()() as db:
        ids = list(
            await db.scalars(
                select(Datasource.id).where(Datasource.status == DatasourceStatus.READY)
            )
        )
    for datasource_id in ids:
        count = await store.client.count(
            store.schema_collection, count_filter=datasource_filter(str(datasource_id)), exact=True
        )
        if count.count == 0:
            log.info("datasource_reindex", datasource_id=str(datasource_id))
            datasources.schedule_indexing(datasource_id)
