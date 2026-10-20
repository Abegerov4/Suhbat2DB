"""Ресурсы прогона на каждую базу: пулы, снимок схемы, индекс Qdrant, эталонные ответы."""

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import structlog
from qdrant_client import AsyncQdrantClient

from app.agent.examples import ExamplesIndexer
from app.agent.retrieval.store import SchemaStore, datasource_filter
from app.schemas.schema_snapshot import SchemaSnapshot
from app.services.target_db import introspect
from evals.paths import DATA, target_url

log = structlog.get_logger()

SCORING_TIMEOUT = "30s"
SNAPSHOTS = DATA / "snapshots"


@dataclass
class Database:
    name: str
    snapshot: SchemaSnapshot
    pool: asyncpg.Pool  # для агента: роль только для чтения, тайм-аут 5 с как в работе
    scoring: asyncpg.Pool  # для подсчёта EX: та же роль, тайм-аут 30 с


@dataclass
class Resources:
    store: SchemaStore
    reindex: bool = False
    databases: dict[str, Database] = field(default_factory=dict)
    _gold: dict[str, list[tuple[Any, ...]] | str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def database(self, name: str) -> Database:
        async with self._lock:
            if name not in self.databases:
                self.databases[name] = await self._open(name)
            return self.databases[name]

    async def _open(self, name: str) -> Database:
        # у роли s2d_reader лимит 20 соединений на кластер (demo_db/roles.sql), а баз в
        # прогоне до 20: пулы маленькие и закрывают простаивающие соединения через секунду
        pool = await asyncpg.create_pool(
            target_url(name), min_size=0, max_size=2, max_inactive_connection_lifetime=1.0
        )
        scoring = await asyncpg.create_pool(
            target_url(name),
            min_size=0,
            max_size=1,
            max_inactive_connection_lifetime=1.0,
            server_settings={"statement_timeout": SCORING_TIMEOUT},
        )
        snapshot = await self._snapshot(name, pool)
        await self._index(snapshot)
        return Database(name, snapshot, pool, scoring)

    async def _snapshot(self, name: str, pool: asyncpg.Pool) -> SchemaSnapshot:
        path = SNAPSHOTS / f"{name}.json"
        if path.exists() and not self.reindex:
            return SchemaSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        async with pool.acquire() as conn:
            snapshot = await introspect(conn, uuid.uuid5(uuid.NAMESPACE_URL, name))
        snapshot.datasource_id = f"eval-{name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(snapshot.model_dump_json(), encoding="utf-8")
        return snapshot

    async def _index(self, snapshot: SchemaSnapshot) -> None:
        """Индексация один раз на версию схемы (метка — хэш снимка без даты)."""
        await self.store.ensure_collections()
        stamp = hashlib.sha256(
            json.dumps(
                snapshot.model_dump(mode="json", exclude={"created_at"}), sort_keys=True
            ).encode()
        ).hexdigest()[:16]
        marker = SNAPSHOTS / f"{snapshot.datasource_id}.{self.store.embedder.name}.indexed"
        count = await self.store.client.count(
            self.store.schema_collection,
            count_filter=datasource_filter(snapshot.datasource_id),
            exact=True,
        )
        if count.count and marker.exists() and marker.read_text() == stamp and not self.reindex:
            return
        log.info("eval_index", datasource=snapshot.datasource_id)
        await ExamplesIndexer(self.store).index(snapshot)
        marker.write_text(stamp)

    async def gold(self, database: str, sql: str) -> list[tuple[Any, ...]] | str:
        """Результат эталонного SQL (кэшируется на прогон); строка — текст ошибки."""
        key = f"{database}\n{sql}"
        if key not in self._gold:
            db = await self.database(database)
            self._gold[key] = await run_sql(db.scoring, sql)
        return self._gold[key]

    async def close(self) -> None:
        for db in self.databases.values():
            await db.pool.close()
            await db.scoring.close()


async def run_sql(pool: asyncpg.Pool, sql: str) -> list[tuple[Any, ...]] | str:
    """Выполнение в транзакции READ ONLY; ошибка возвращается текстом, а не исключением."""
    try:
        async with pool.acquire() as conn, conn.transaction(readonly=True):
            return [tuple(r.values()) for r in await conn.fetch(sql)]
    except (TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
        return f"{type(e).__name__}: {str(e)[:200]}"


def make_store(client: AsyncQdrantClient, embedder: Any) -> SchemaStore:
    return SchemaStore(client, embedder)
