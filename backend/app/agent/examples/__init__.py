"""Проверенные пары «вопрос → SQL» для динамического few-shot.

Каждый файл описывает требуемые таблицы: примеры загружаются только в источник,
схема которого их содержит (сейчас — демо-БД). Корректность примеров проверяет
тест tests/validator/test_demo_db.py.
"""

import json
from pathlib import Path

from app.agent.retrieval.store import SchemaStore, SqlExample
from app.schemas.schema_snapshot import SchemaSnapshot

HERE = Path(__file__).resolve().parent


def examples_for(snapshot: SchemaSnapshot) -> list[SqlExample]:
    tables = {t.name for t in snapshot.tables}
    result: list[SqlExample] = []
    for path in sorted(HERE.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data["requires_tables"]) <= tables:
            result.extend(SqlExample(e["question"], e["sql"]) for e in data["examples"])
    return result


class ExamplesIndexer:
    """SchemaIndexer: схема источника + подходящие ему примеры."""

    def __init__(self, store: SchemaStore) -> None:
        self.store = store

    async def index(self, snapshot: SchemaSnapshot) -> None:
        await self.store.index(snapshot)
        await self.store.add_examples(snapshot.datasource_id, examples_for(snapshot))

    async def delete(self, datasource_id: str) -> None:
        await self.store.delete(datasource_id)
