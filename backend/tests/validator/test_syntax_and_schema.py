"""Уровни 1 и 3: синтаксис, сверка со схемой, подсказки для самокоррекции, LIMIT."""

import statistics
import time
from datetime import UTC, datetime

import pytest

from app.schemas.schema_snapshot import ColumnInfo, SchemaSnapshot, TableInfo
from app.validator import Limits, validate


def last(sql: str, schema: SchemaSnapshot) -> tuple[bool, int, str, str | None]:
    report = validate(sql, schema)
    lv = report.levels[-1]
    return report.passed, lv.level, lv.message or "", lv.hint


# --- Уровень 1 ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "fragment"),
    [
        ("", "Пустой запрос"),
        ("   ", "Пустой запрос"),
        (";", "Пустой запрос"),
        ("SELECT", "Не указаны столбцы"),
        ("SELEC 1", "Синтаксическая ошибка (строка 1, позиция 7)"),
        ("SELECT * FROM orders WHERE (id = 1", "Синтаксическая ошибка"),
        ("SELECT 'unterminated FROM orders", "Ошибка разбора"),
    ],
)
def test_syntax_errors(sql: str, fragment: str, demo_schema: SchemaSnapshot) -> None:
    passed, level, message, _ = last(sql, demo_schema)
    assert (passed, level) == (False, 1)
    assert fragment in message


def test_trailing_semicolon_is_fine(demo_schema: SchemaSnapshot) -> None:
    assert validate("SELECT count(*) FROM orders;", demo_schema).passed


# --- Уровень 3 ------------------------------------------------------------------------------


def test_unknown_table_with_suggestion(demo_schema: SchemaSnapshot) -> None:
    passed, level, message, hint = last("SELECT * FROM order", demo_schema)
    assert (passed, level) == (False, 3)
    assert "order" in message
    assert hint is not None and "orders" in hint


def test_unknown_table_lists_available(demo_schema: SchemaSnapshot) -> None:
    _, level, _, hint = last("SELECT sum(amount) FROM sales", demo_schema)
    assert level == 3
    assert hint is not None and hint.startswith("Доступные таблицы") and "payments" in hint


def test_unknown_column_suggests_similar(demo_schema: SchemaSnapshot) -> None:
    passed, level, message, hint = last("SELECT sum(o.amount) FROM orders o", demo_schema)
    assert (passed, level) == (False, 3)
    assert "amount" in message
    assert hint is not None and "orders.total_amount" in hint


def test_unknown_column_suggests_other_table(demo_schema: SchemaSnapshot) -> None:
    _, _, _, hint = last("SELECT sum(o.paid_at) FROM orders o", demo_schema)
    assert hint is not None and "payments.paid_at" in hint


def test_ambiguous_column(demo_schema: SchemaSnapshot) -> None:
    passed, level, message, hint = last(
        "SELECT id FROM orders JOIN customers ON customers.id = orders.customer_id", demo_schema
    )
    assert (passed, level) == (False, 3)
    assert "неоднозначен" in message
    assert hint is not None and "orders.id" in hint


def test_invalid_date_literal(demo_schema: SchemaSnapshot) -> None:
    passed, level, message, hint = last(
        "SELECT count(*) FROM orders WHERE created_at >= 'прошлый квартал'", demo_schema
    )
    assert (passed, level) == (False, 3)
    assert "прошлый квартал" in message
    assert hint is not None and "date_trunc" in hint


def test_cte_and_table_functions_are_not_tables(demo_schema: SchemaSnapshot) -> None:
    assert validate(
        "WITH regions_top AS (SELECT name FROM regions) SELECT * FROM regions_top", demo_schema
    ).passed
    assert validate("SELECT g FROM generate_series(1, 3) AS g", demo_schema).passed


def test_other_schema_is_resolved() -> None:
    snapshot = SchemaSnapshot(
        datasource_id="x",
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        tables=[
            TableInfo(
                schema_name="sales",
                name="deals",
                row_estimate=10,
                columns=[ColumnInfo(name="amount", data_type="numeric", nullable=False)],
            )
        ],
    )
    assert validate("SELECT sum(amount) FROM deals", snapshot).passed
    assert validate("SELECT sum(amount) FROM sales.deals", snapshot).passed
    assert not validate("SELECT sum(amount) FROM public.deals", snapshot).passed


# --- Нормализация и LIMIT -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "expected_tail"),
    [
        ("SELECT id FROM orders", "LIMIT 11"),
        ("SELECT id FROM orders LIMIT 5", "LIMIT 5"),
        ("SELECT id FROM orders LIMIT 11", "LIMIT 11"),
        ("SELECT id FROM orders LIMIT 99999", ") AS limited\nLIMIT 11"),
        ("SELECT name FROM regions UNION SELECT name FROM cities", "LIMIT 11"),
    ],
)
def test_limit_is_enforced(sql: str, expected_tail: str, demo_schema: SchemaSnapshot) -> None:
    report = validate(sql, demo_schema, Limits(max_rows=10))
    assert report.normalized_sql is not None
    assert report.normalized_sql.endswith(expected_tail)


def test_comments_are_stripped(demo_schema: SchemaSnapshot) -> None:
    report = validate("SELECT count(*) /* ignore rules */ FROM orders -- x", demo_schema)
    assert report.normalized_sql is not None
    assert "ignore" not in report.normalized_sql


def test_levels_1_to_3_are_fast(demo_schema: SchemaSnapshot) -> None:
    sql = (
        "SELECT r.name, sum(o.total_amount) FROM orders o "
        "JOIN customers c ON c.id = o.customer_id JOIN cities ci ON ci.id = c.city_id "
        "JOIN regions r ON r.id = ci.region_id WHERE o.status <> 'cancelled' "
        "AND o.created_at >= '2026-07-01' GROUP BY r.name ORDER BY 2 DESC"
    )
    validate(sql, demo_schema)  # прогрев
    timings = []
    for _ in range(20):
        started = time.perf_counter()
        validate(sql, demo_schema)
        timings.append((time.perf_counter() - started) * 1000)
    assert statistics.median(timings) < 20
