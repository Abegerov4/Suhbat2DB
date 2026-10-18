"""Индекс схемы и примеров «вопрос → SQL» в Qdrant (гибридный поиск: dense + BM25, RRF).

Индексируются метаданные, а не данные пользователя: таблицы, столбцы с комментариями
и значения категориальных столбцов (для value linking: «Алматы» → regions.name).
"""

import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from qdrant_client import AsyncQdrantClient, models

from app.agent.retrieval.embeddings import Embedder
from app.agent.retrieval.sparse import sparse_document, sparse_query
from app.schemas.schema_snapshot import SchemaSnapshot

DocKind = Literal["table", "column", "value"]
DENSE, SPARSE = "dense", "bm25"
SearchMode = Literal["hybrid", "dense", "sparse"]
NAMESPACE = uuid.UUID("5a1b2c3d-0000-4000-8000-5ab0a7d2d000")


@dataclass(frozen=True)
class SchemaDoc:
    kind: DocKind
    schema: str
    table: str
    text: str
    column: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class Hit:
    doc: SchemaDoc
    score: float


@dataclass(frozen=True)
class SqlExample:
    question: str
    sql: str


def build_documents(snapshot: SchemaSnapshot) -> list[SchemaDoc]:
    docs: list[SchemaDoc] = []
    for t in snapshot.tables:
        columns = ", ".join(c.name for c in t.columns)
        docs.append(
            SchemaDoc(
                "table",
                t.schema_name,
                t.name,
                f"Таблица {t.name}: {t.comment or ''}. Столбцы: {columns}",
            )
        )
        for c in t.columns:
            fk = f", ссылается на {c.fk}" if c.fk else ""
            docs.append(
                SchemaDoc(
                    "column",
                    t.schema_name,
                    t.name,
                    f"Столбец {t.name}.{c.name} ({c.data_type}{fk}): {c.comment or ''}",
                    column=c.name,
                )
            )
            for value in c.sample_values or []:
                docs.append(
                    SchemaDoc(
                        "value",
                        t.schema_name,
                        t.name,
                        f"Значение «{value}» в {t.name}.{c.name}: {c.comment or ''}",
                        column=c.name,
                        value=value,
                    )
                )
    return docs


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def datasource_filter(datasource_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(key="datasource_id", match=models.MatchValue(value=datasource_id))
        ]
    )


class SchemaStore:
    """Коллекции именуются по модели эмбеддингов: модели можно сравнивать без переиндексации."""

    def __init__(self, client: AsyncQdrantClient, embedder: Embedder) -> None:
        self.client = client
        self.embedder = embedder
        self.schema_collection = f"schema_elements__{slug(embedder.name)}"
        self.examples_collection = f"sql_examples__{slug(embedder.name)}"

    async def ensure_collections(self) -> None:
        for name in (self.schema_collection, self.examples_collection):
            if await self.client.collection_exists(name):
                continue
            await self.client.create_collection(
                name,
                vectors_config={
                    DENSE: models.VectorParams(
                        size=self.embedder.dimension, distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
                },
            )
            await self.client.create_payload_index(
                name, "datasource_id", field_schema=models.PayloadSchemaType.KEYWORD
            )

    async def _replace(
        self, collection: str, datasource_id: str, texts: list[str], payloads: list[dict[str, Any]]
    ) -> None:
        await self.ensure_collections()
        await self.client.delete(
            collection,
            points_selector=models.FilterSelector(filter=datasource_filter(datasource_id)),
        )
        if not texts:
            return
        vectors = await self.embedder.embed(texts)
        points = []
        for text, payload, vector in zip(texts, payloads, vectors, strict=True):
            indices, values = sparse_document(text)
            key = f"{datasource_id}|{payload.get('kind')}|{text}"
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid5(NAMESPACE, key)),
                    vector={
                        DENSE: vector,
                        SPARSE: models.SparseVector(indices=indices, values=values),
                    },
                    payload={"datasource_id": datasource_id, "text": text, **payload},
                )
            )
        await self.client.upsert(collection, points=points, wait=True)

    # --- SchemaIndexer (services/indexer.py) ---

    async def index(self, snapshot: SchemaSnapshot) -> None:
        docs = build_documents(snapshot)
        await self._replace(
            self.schema_collection,
            snapshot.datasource_id,
            [d.text for d in docs],
            [
                {
                    "kind": d.kind,
                    "schema": d.schema,
                    "table": d.table,
                    "column": d.column,
                    "value": d.value,
                }
                for d in docs
            ],
        )

    async def delete(self, datasource_id: str) -> None:
        await self.ensure_collections()
        for collection in (self.schema_collection, self.examples_collection):
            await self.client.delete(
                collection,
                points_selector=models.FilterSelector(filter=datasource_filter(datasource_id)),
            )

    # --- Поиск ---

    async def _hybrid(
        self,
        collection: str,
        datasource_id: str,
        query: str,
        limit: int,
        mode: SearchMode = "hybrid",
    ) -> list[models.ScoredPoint]:
        flt = datasource_filter(datasource_id)
        prefetch = []
        if mode in ("hybrid", "dense"):
            [dense] = await self.embedder.embed([query])
            prefetch.append(models.Prefetch(query=dense, using=DENSE, filter=flt, limit=limit))
        indices, values = sparse_query(query)
        if mode in ("hybrid", "sparse") and indices:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(indices=indices, values=values),
                    using=SPARSE,
                    filter=flt,
                    limit=limit,
                )
            )
        if not prefetch:
            return []
        response = await self.client.query_points(
            collection,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return response.points

    async def search(
        self, datasource_id: str, query: str, limit: int, mode: SearchMode = "hybrid"
    ) -> list[Hit]:
        points = await self._hybrid(self.schema_collection, datasource_id, query, limit, mode)
        hits = []
        for p in points:
            pl = p.payload or {}
            hits.append(
                Hit(
                    SchemaDoc(
                        pl["kind"],
                        pl["schema"],
                        pl["table"],
                        pl["text"],
                        pl.get("column"),
                        pl.get("value"),
                    ),
                    p.score,
                )
            )
        return hits

    async def add_examples(self, datasource_id: str, examples: list[SqlExample]) -> None:
        await self._replace(
            self.examples_collection,
            datasource_id,
            [e.question for e in examples],
            [{"kind": "example", "sql": e.sql} for e in examples],
        )

    async def search_examples(self, datasource_id: str, question: str, k: int) -> list[SqlExample]:
        if k <= 0:
            return []
        points = await self._hybrid(self.examples_collection, datasource_id, question, k)
        return [SqlExample((p.payload or {})["text"], (p.payload or {})["sql"]) for p in points]
