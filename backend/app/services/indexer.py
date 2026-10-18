"""Индексация схемы в векторную БД. Реализация — в роли 5 (schema linking)."""

from typing import Protocol

from app.schemas.schema_snapshot import SchemaSnapshot


class SchemaIndexer(Protocol):
    async def index(self, snapshot: SchemaSnapshot) -> None: ...

    async def delete(self, datasource_id: str) -> None: ...


class NoopIndexer:
    async def index(self, snapshot: SchemaSnapshot) -> None:
        return None

    async def delete(self, datasource_id: str) -> None:
        return None


_indexer: SchemaIndexer = NoopIndexer()


def get_indexer() -> SchemaIndexer:
    return _indexer


def set_indexer(indexer: SchemaIndexer) -> None:
    """В роли 5 пустая реализация заменяется индексом в Qdrant (app.agent.factory)."""
    global _indexer
    _indexer = indexer
