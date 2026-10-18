"""Уровни 4–5 на целевой тестовой БД (regions × 5, orders × 1000, events × 20 000)."""

import asyncpg
import pytest

from app.services.target_db import introspect
from app.validator import ExecutionError, Limits, execute_readonly, explain, validate
from tests.conftest import requires_db

pytestmark = requires_db


# --- Уровень 4 ------------------------------------------------------------------------------


async def test_explain_passes_normal_query(reader_conn: asyncpg.Connection) -> None:
    lv = await explain(
        "SELECT r.name, count(*) FROM orders o JOIN regions r ON r.id = o.region_id GROUP BY 1",
        reader_conn,
        Limits(),
    )
    assert lv.passed and lv.level == 4
    assert "Оценка стоимости" in (lv.message or "")


async def test_explain_detects_cartesian_product(reader_conn: asyncpg.Connection) -> None:
    lv = await explain("SELECT count(*) FROM events a, events b", reader_conn, Limits())
    assert not lv.passed
    assert "Декартово произведение" in (lv.message or "")
    assert lv.hint is not None and "JOIN" in lv.hint


async def test_explain_allows_keyed_self_join(reader_conn: asyncpg.Connection) -> None:
    lv = await explain(
        "SELECT count(*) FROM events a JOIN events b ON b.id = a.id + 1", reader_conn, Limits()
    )
    assert lv.passed, lv.message


async def test_explain_cost_limit(reader_conn: asyncpg.Connection) -> None:
    lv = await explain("SELECT * FROM events", reader_conn, Limits(max_explain_cost=10))
    assert not lv.passed
    assert "слишком тяжёлый" in (lv.message or "")


async def test_explain_reports_planner_error(reader_conn: asyncpg.Connection) -> None:
    lv = await explain("SELECT * FROM events WHERE created_at > 'не дата'", reader_conn, Limits())
    assert not lv.passed
    assert "Ошибка планировщика" in (lv.message or "")


# --- Уровень 5 ------------------------------------------------------------------------------


async def test_execute_returns_typed_json(reader_conn: asyncpg.Connection) -> None:
    result = await execute_readonly(
        "SELECT r.name, sum(o.amount) AS total, min(e.created_at) AS first, NULL AS nothing "
        "FROM regions r JOIN orders o ON o.region_id = r.id "
        "JOIN events e ON e.id = o.id GROUP BY r.name ORDER BY r.name",
        reader_conn,
        Limits(),
    )
    assert [c.name for c in result.columns] == ["name", "total", "first", "nothing"]
    assert [c.type for c in result.columns][:2] == ["text", "numeric"]
    assert result.row_count == 5 and not result.truncated
    name, total, first, nothing = result.rows[0]
    assert name == "Регион 1"
    assert isinstance(total, int | float)
    assert isinstance(first, str) and first.startswith("2026-01-01")
    assert nothing is None


async def test_execute_truncates(reader_conn: asyncpg.Connection) -> None:
    result = await execute_readonly("SELECT * FROM events", reader_conn, Limits(max_rows=100))
    assert result.row_count == 100
    assert result.truncated


async def test_execute_truncates_by_size(reader_conn: asyncpg.Connection) -> None:
    result = await execute_readonly(
        "SELECT * FROM events", reader_conn, Limits(max_rows=10_000, max_result_bytes=10_000)
    )
    assert result.truncated
    assert 0 < result.row_count < 10_000


async def test_execute_timeout(reader_conn: asyncpg.Connection) -> None:
    with pytest.raises(ExecutionError) as e:
        await execute_readonly(
            "SELECT count(*) FROM events a, events b", reader_conn, Limits(statement_timeout_ms=200)
        )
    assert e.value.result.level == 5
    assert "Превышено время" in (e.value.result.message or "")


async def test_execute_runtime_error(reader_conn: asyncpg.Connection) -> None:
    with pytest.raises(ExecutionError) as e:
        await execute_readonly(
            "SELECT 1 / (count(*) - count(*)) FROM orders", reader_conn, Limits()
        )
    assert "division by zero" in (e.value.result.message or "")


async def test_read_only_transaction_even_for_superuser(
    superuser_conn: asyncpg.Connection,
) -> None:
    """Defense in depth: если запись прошла бы мимо уровней 1–4, транзакция её не допустит."""
    with pytest.raises(ExecutionError) as e:
        await execute_readonly("DELETE FROM orders", superuser_conn, Limits())
    assert "read-only" in (e.value.result.message or "")
    assert await superuser_conn.fetchval("SELECT count(*) FROM orders") == 1000


async def test_full_pipeline(reader_conn: asyncpg.Connection) -> None:
    import uuid

    snapshot = await introspect(reader_conn, uuid.uuid4())
    report = validate("SELECT region_id, count(*) FROM events GROUP BY 1", snapshot)
    assert report.passed and report.normalized_sql
    assert (await explain(report.normalized_sql, reader_conn, Limits())).passed
    result = await execute_readonly(report.normalized_sql, reader_conn, Limits())
    assert result.row_count == 5
