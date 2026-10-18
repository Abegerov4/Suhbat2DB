"""Уровень 1: синтаксис. Запрос разбирается sqlglot и должен быть ровно одним выражением."""

import logging

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

from app.schemas.agent import ValidationLevelResult

DIALECT = "postgres"

# sqlglot пишет WARNING при разборе неизвестных команд как Command — это ожидаемо
logging.getLogger("sqlglot").setLevel(logging.ERROR)


def result(
    passed: bool, message: str, hint: str | None = None, fatal: bool = False
) -> ValidationLevelResult:
    return ValidationLevelResult(
        level=1, name="syntax", passed=passed, message=message, hint=hint, fatal=fatal
    )


def check_syntax(sql: str) -> tuple[ValidationLevelResult, exp.Expr | None]:
    if not sql.strip():
        return result(False, "Пустой запрос"), None
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as e:
        error = e.errors[0] if e.errors else {}
        where = f" (строка {error.get('line')}, позиция {error.get('col')})" if error else ""
        context = error.get("highlight") or ""
        return (
            result(
                False,
                f"Синтаксическая ошибка{where}: {error.get('description', str(e))}",
                hint=f"Проверьте фрагмент рядом с «{context}»" if context else None,
            ),
            None,
        )
    except TokenError as e:
        return result(False, f"Ошибка разбора: {e}", hint="Проверьте парность кавычек"), None

    if not statements:
        return result(False, "Пустой запрос"), None
    if len(statements) > 1:
        # несколько выражений — классический способ спрятать DROP после SELECT
        return result(False, "В запросе несколько SQL-выражений", fatal=True), None
    statement = statements[0]
    if isinstance(statement, exp.Select) and not statement.expressions:
        return result(False, "Не указаны столбцы в SELECT"), None
    return result(True, "Синтаксис корректен"), statement
