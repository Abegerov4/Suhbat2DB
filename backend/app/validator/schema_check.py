"""Уровень 3: сверка со схемой БД.

Проверяет, что таблицы и столбцы существуют и ссылки на столбцы однозначны.
Ошибки сопровождаются подсказкой (hint) — её получает генератор SQL при самокоррекции.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import get_close_matches

from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify
from sqlglot.schema import MappingSchema

from app.schemas.agent import ValidationLevelResult
from app.schemas.schema_snapshot import SchemaSnapshot
from app.validator.syntax import DIALECT

DEFAULT_SCHEMA = "public"
UNRESOLVED_RE = re.compile(r"Column '([^']+)' could not be resolved")
UNKNOWN_RE = re.compile(r"Unknown column: (\S+)")


@dataclass
class SchemaIndex:
    """Снимок схемы в виде, удобном для поиска таблиц и столбцов."""

    columns: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    schemas_by_table: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_snapshot(cls, snapshot: SchemaSnapshot) -> "SchemaIndex":
        index = cls()
        for t in snapshot.tables:
            index.columns[(t.schema_name, t.name)] = {c.name: c.data_type for c in t.columns}
            index.schemas_by_table.setdefault(t.name, []).append(t.schema_name)
        return index

    def resolve(self, table: str, schema: str | None) -> str | None:
        """Схема таблицы с учётом search_path: сначала public, затем единственная другая."""
        if schema:
            return schema if (schema, table) in self.columns else None
        candidates = self.schemas_by_table.get(table, [])
        if DEFAULT_SCHEMA in candidates:
            return DEFAULT_SCHEMA
        return candidates[0] if len(candidates) == 1 else None

    def mapping(self) -> MappingSchema:
        nested: dict[str, object] = {}
        for (schema, table), cols in self.columns.items():
            nested.setdefault(schema, {})[table] = dict(cols)  # type: ignore[index]
        return MappingSchema(nested, dialect=DIALECT, normalize=False)


def result(passed: bool, message: str, hint: str | None = None) -> ValidationLevelResult:
    return ValidationLevelResult(level=3, name="schema", passed=passed, message=message, hint=hint)


def close(name: str, candidates: list[str], n: int = 3) -> list[str]:
    return get_close_matches(name.lower(), candidates, n=n, cutoff=0.5)


def query_tables(expression: exp.Expr) -> list[exp.Table]:
    """Ссылки на реальные таблицы (без CTE и табличных функций вроде generate_series)."""
    cte_names = {cte.alias_or_name for cte in expression.find_all(exp.CTE)}
    return [
        t
        for t in expression.find_all(exp.Table)
        if isinstance(t.this, exp.Identifier) and not (not t.db and t.name in cte_names)
    ]


def column_hint(
    column: str, index: SchemaIndex, used: list[tuple[str, str]]
) -> tuple[str, str | None]:
    """Сообщение и подсказка для нерешённого столбца: неоднозначен или не существует."""
    owners = [f"{t}.{column}" for s, t in used if column in index.columns[(s, t)]]
    if len(owners) > 1:
        return (
            f"Столбец «{column}» неоднозначен: есть в таблицах {', '.join(owners)}",
            f"Укажите таблицу явно, например {owners[0]}",
        )
    exact = [f"{t}.{column}" for (s, t), cols in index.columns.items() if column in cols]
    in_query = [f"{t}.{c}" for s, t in used for c in index.columns[(s, t)]]
    matches = close(column, [x.split(".", 1)[1] for x in in_query])
    similar = [x for x in in_query if x.split(".", 1)[1] in matches]
    # похожие столбцы таблиц запроса + столбцы с тем же именем в других таблицах
    suggestions = list(dict.fromkeys(similar[:2] + exact[:2]))
    if not suggestions:  # ищем во всей схеме: возможно, нужна другая таблица
        everywhere = [f"{t}.{c}" for (s, t), cols in index.columns.items() for c in cols]
        matches = close(column, [x.split(".", 1)[1] for x in everywhere])
        suggestions = [x for x in everywhere if x.split(".", 1)[1] in matches][:3]
    hint = f"Возможно, имелось в виду: {', '.join(suggestions)}" if suggestions else None
    if hint is None and used:
        s, t = used[0]
        hint = f"Столбцы {t}: {', '.join(list(index.columns[(s, t)])[:20])}"
    return f"Столбца «{column}» нет в таблицах запроса", hint


# Строки, которые PostgreSQL понимает как дату/время помимо ISO-формата
SPECIAL_TEMPORAL = {"now", "today", "tomorrow", "yesterday", "epoch", "infinity", "-infinity"}


def temporal_errors(expression: exp.Expr, mapping: MappingSchema) -> list[str]:
    """Сравнение даты со строкой, которая не является датой, — частая ошибка генерации
    («created_at >= 'прошлый квартал'»). PostgreSQL отвергнет такой запрос при выполнении."""
    annotated = annotate_types(expression, schema=mapping, dialect=DIALECT)
    errors = []
    for cmp in annotated.find_all(exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE):
        for col, lit in ((cmp.left, cmp.right), (cmp.right, cmp.left)):
            if (
                isinstance(col, exp.Column)
                and isinstance(lit, exp.Literal)
                and lit.is_string
                and col.type is not None
                and col.type.is_type(*exp.DataType.TEMPORAL_TYPES)
                and not is_date_literal(lit.this)
            ):
                errors.append(f"«{lit.this}» сравнивается с датой {col.sql()}")
    return errors


def is_date_literal(value: str) -> bool:
    if value.strip().lower() in SPECIAL_TEMPORAL:
        return True
    for parse in (datetime.fromisoformat, date.fromisoformat):
        try:
            parse(value)
        except ValueError:
            continue
        return True
    return False


def check_schema(expression: exp.Expr, snapshot: SchemaSnapshot) -> ValidationLevelResult:
    index = SchemaIndex.from_snapshot(snapshot)
    # как в PostgreSQL: идентификаторы без кавычек приводятся к нижнему регистру
    expression = normalize_identifiers(expression.copy(), dialect=DIALECT)

    used: list[tuple[str, str]] = []
    for table in query_tables(expression):
        schema = index.resolve(table.name, table.db or None)
        if schema is None:
            names = sorted({t for _, t in index.columns})
            suggestions = close(table.name, names)
            return result(
                False,
                f"Таблицы «{table.sql(dialect=DIALECT)}» нет в базе данных",
                hint=(
                    f"Возможно, имелось в виду: {', '.join(suggestions)}"
                    if suggestions
                    else f"Доступные таблицы: {', '.join(names)}"
                ),
            )
        table.set("db", exp.to_identifier(schema))
        used.append((schema, table.name))

    mapping = index.mapping()
    try:
        qualified = qualify(
            expression,
            schema=mapping,
            dialect=DIALECT,
            db=DEFAULT_SCHEMA,
            validate_qualify_columns=True,
            quote_identifiers=False,
        )
    except OptimizeError as e:
        text = str(e)
        match = UNRESOLVED_RE.search(text) or UNKNOWN_RE.search(text)
        if match:
            message, hint = column_hint(match.group(1), index, used)
            return result(False, message, hint)
        return result(False, f"Ошибка сверки со схемой: {text}")
    except SqlglotError as e:
        return result(False, f"Ошибка сверки со схемой: {e}")

    try:
        errors = temporal_errors(qualified, mapping)
    except SqlglotError:
        errors = []  # вывод типов — вспомогательная проверка, её сбой не блокирует запрос
    if errors:
        return result(
            False,
            "Строка не является датой: " + "; ".join(errors),
            hint="Используйте даты в формате 'YYYY-MM-DD' или выражения "
            "date_trunc('quarter', now()) - interval '3 months'",
        )
    return result(True, "Все таблицы и столбцы существуют")
