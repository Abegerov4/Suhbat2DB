"""Уровни 1–2 на наборах атак и безобидных запросов (evals/datasets/unsafe)."""

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.schema_snapshot import SchemaSnapshot
from app.validator import validate
from tests.validator.conftest import ATTACKS, BENIGN


def test_dataset_sizes() -> None:
    assert len(ATTACKS) >= 60
    assert len(BENIGN) >= 30


@pytest.mark.parametrize("case", ATTACKS, ids=[c["id"] for c in ATTACKS])
def test_attack_is_blocked(case: dict[str, Any], demo_schema: SchemaSnapshot) -> None:
    report = validate(case["sql"], demo_schema)
    assert not report.passed
    last = report.levels[-1]
    # атака останавливается до сверки со схемой: на синтаксисе или политике
    assert last.level in (1, 2)
    # всё, что удалось разобрать, — фатально (самокоррекция не пытается «починить» атаку)
    if last.level == 2 or "несколько" in (last.message or ""):
        assert last.fatal


def test_almost_all_attacks_are_fatal(demo_schema: SchemaSnapshot) -> None:
    fatal = sum(validate(c["sql"], demo_schema).levels[-1].fatal for c in ATTACKS)
    # NOTIFY sqlglot не разбирает: он блокируется как синтаксическая ошибка
    assert fatal >= len(ATTACKS) - 1


@pytest.mark.parametrize("case", BENIGN, ids=[c["id"] for c in BENIGN])
def test_benign_is_allowed(case: dict[str, Any], demo_schema: SchemaSnapshot) -> None:
    report = validate(case["sql"], demo_schema)
    assert report.passed, report.levels[-1]
    assert [lv.level for lv in report.levels] == [1, 2, 3]
    assert report.normalized_sql


# --- Property-based: опасный фрагмент в любом месте допустимого запроса блокируется ---------

DANGEROUS_SUBQUERIES = [
    "DELETE FROM orders RETURNING id",
    "UPDATE orders SET total_amount = 0 RETURNING id",
    "INSERT INTO regions VALUES (99, 'X', 'city') RETURNING id",
]
DANGEROUS_EXPRESSIONS = [
    "pg_sleep(5)",
    "pg_read_file('/etc/passwd')",
    "set_config('statement_timeout', '0', false)",
    "nextval('s')",
    "lo_import('/tmp/x')",
    "(SELECT count(*) FROM pg_shadow)",
]
CASE_CHANGES = st.sampled_from([str.lower, str.upper, str.title])


@settings(max_examples=150, deadline=None)
@given(
    sub=st.sampled_from(DANGEROUS_SUBQUERIES),
    template=st.sampled_from(
        [
            "WITH x AS ({sub}) SELECT * FROM x",
            "WITH a AS (SELECT 1), x AS ({sub}) SELECT * FROM a",
            "SELECT * FROM orders WHERE id IN (WITH x AS ({sub}) SELECT id FROM x)",
        ]
    ),
    case=CASE_CHANGES,
)
def test_dml_hidden_in_cte_is_blocked(
    sub: str, template: str, case: Any, demo_schema: SchemaSnapshot
) -> None:
    report = validate(case(template.format(sub=sub)), demo_schema)
    assert not report.passed
    assert report.levels[-1].level in (1, 2)


@settings(max_examples=150, deadline=None)
@given(
    expr=st.sampled_from(DANGEROUS_EXPRESSIONS),
    template=st.sampled_from(
        [
            "SELECT {expr}",
            "SELECT id, {expr} AS x FROM orders",
            "SELECT count(*) FROM orders WHERE ({expr}) IS NOT NULL",
            "SELECT status FROM orders GROUP BY status HAVING count(*) > 0 AND ({expr}) IS NULL",
            "SELECT * FROM regions UNION ALL SELECT id, {expr}::text, 'city' FROM regions",
            "SELECT * FROM (SELECT {expr} AS x) AS t",
        ]
    ),
    case=CASE_CHANGES,
    comment=st.sampled_from(["", " /* ok */ ", " -- note\n"]),
)
def test_dangerous_expression_anywhere_is_blocked(
    expr: str, template: str, case: Any, comment: str, demo_schema: SchemaSnapshot
) -> None:
    sql = case(template.format(expr=expr)).replace(" FROM ", f"{comment or ' '}FROM ", 1)
    report = validate(sql, demo_schema)
    assert not report.passed
    assert report.levels[-1].level in (1, 2)
    assert report.levels[-1].fatal
