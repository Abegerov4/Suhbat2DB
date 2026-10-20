"""Многоуровневая проверка SQL (docs/validator.md, CONTRACTS §3).

report = validate(sql, snapshot)                       # уровни 1–3, без БД
if report.passed:
    level4 = await explain(report.normalized_sql, conn, limits)
    result = await execute_readonly(report.normalized_sql, conn, limits)  # уровень 5
"""

from sqlglot import exp

from app.schemas.agent import ValidationReport
from app.schemas.schema_snapshot import SchemaSnapshot
from app.validator.executor import ExecutionError, execute_readonly
from app.validator.explain import explain
from app.validator.limits import Limits
from app.validator.policy import check_policy
from app.validator.schema_check import check_schema
from app.validator.syntax import DIALECT, check_syntax

__all__ = ["ExecutionError", "Limits", "execute_readonly", "explain", "validate"]


def apply_limit(expression: exp.Expr, max_rows: int) -> exp.Expr:
    """Внешний LIMIT не больше max_rows + 1: лишняя строка — признак усечения результата."""
    cap = max_rows + 1
    assert isinstance(expression, exp.Query)
    limit = expression.args.get("limit")
    if limit is None and expression.args.get("fetch") is None:
        return expression.limit(cap, copy=False)
    value = limit.expression if isinstance(limit, exp.Limit) else None
    if isinstance(value, exp.Literal) and value.is_int and int(value.this) <= cap:
        return expression  # пользователь сам ограничил выборку
    return exp.select("*").from_(expression.subquery("limited")).limit(cap)


def validate(
    sql: str,
    snapshot: SchemaSnapshot,
    limits: Limits | None = None,
    *,
    schema_check: bool = True,
) -> ValidationReport:
    """Уровни 1–3. Проверка останавливается на первом непройденном уровне.

    schema_check=False — только для ablation-эксперимента (evals): уровень 3 пропускается.
    """
    limits = limits or Limits()
    level1, expression = check_syntax(sql)
    if expression is None:
        return ValidationReport(passed=False, levels=[level1])

    level2 = check_policy(expression)
    if not level2.passed:
        return ValidationReport(passed=False, levels=[level1, level2])

    levels = [level1, level2]
    if schema_check:
        level3 = check_schema(expression, snapshot)
        levels.append(level3)
        if not level3.passed:
            return ValidationReport(passed=False, levels=levels)

    normalized = apply_limit(expression.copy(), limits.max_rows)
    return ValidationReport(
        passed=True,
        levels=levels,
        normalized_sql=normalized.sql(dialect=DIALECT, pretty=True, comments=False),
    )
