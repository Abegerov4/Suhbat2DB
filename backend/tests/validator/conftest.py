import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from app.schemas.schema_snapshot import SchemaSnapshot

HERE = Path(__file__).resolve().parent
DATASETS = HERE.parents[2] / "evals" / "datasets" / "unsafe"


def load_jsonl(name: str) -> list[dict[str, Any]]:
    with (DATASETS / name).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


ATTACKS = load_jsonl("sql_attacks.jsonl")
BENIGN = load_jsonl("sql_benign.jsonl")


@pytest.fixture(scope="session")
def demo_schema() -> SchemaSnapshot:
    """Снимок схемы демо-БД (tests/validator/demo_schema.json, получен через API)."""
    return SchemaSnapshot.model_validate(
        json.loads((HERE / "demo_schema.json").read_text(encoding="utf-8"))
    )


@pytest.fixture
async def reader_conn(target_urls: dict[str, str]) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(target_urls["reader"])
    yield conn
    await conn.close()


@pytest.fixture
async def superuser_conn(target_urls: dict[str, str]) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(target_urls["superuser"])
    yield conn
    await conn.close()
