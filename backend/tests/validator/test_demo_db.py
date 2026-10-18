"""Все безобидные запросы проходят уровни 1–5 на настоящей демо-БД под ролью s2d_reader.

Запускается локально (`make test-backend` передаёт TEST_DEMO_DB_URL); в CI пропускается.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest

from app.schemas.schema_snapshot import SchemaSnapshot
from app.validator import Limits, execute_readonly, explain, validate
from tests.validator.conftest import BENIGN

DEMO_URL = os.environ.get("TEST_DEMO_DB_URL")

pytestmark = pytest.mark.skipif(not DEMO_URL, reason="TEST_DEMO_DB_URL не задан")


@pytest.fixture
async def demo_conn() -> AsyncIterator[asyncpg.Connection]:
    assert DEMO_URL
    conn = await asyncpg.connect(DEMO_URL)
    yield conn
    await conn.close()


@pytest.mark.parametrize("case", BENIGN, ids=[c["id"] for c in BENIGN])
async def test_benign_runs_on_demo(
    case: dict[str, Any], demo_schema: SchemaSnapshot, demo_conn: asyncpg.Connection
) -> None:
    limits = Limits()
    report = validate(case["sql"], demo_schema, limits)
    assert report.passed and report.normalized_sql
    level4 = await explain(report.normalized_sql, demo_conn, limits)
    assert level4.passed, level4.message
    result = await execute_readonly(report.normalized_sql, demo_conn, limits)
    assert result.row_count >= 0
