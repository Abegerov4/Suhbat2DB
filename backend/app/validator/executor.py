"""Уровень 5: выполнение в изолированной транзакции «только чтение» с лимитами.

Это последний рубеж: даже если уровни 1–4 пропустят опасный запрос, роль без прав
на запись и READ ONLY-транзакция не дадут изменить данные (docs/demo_db.md).
"""

import json
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal
from typing import Any

import asyncpg

from app.schemas.agent import ColumnMeta, QueryResult, ValidationLevelResult
from app.services.target_db import Conn
from app.validator.limits import Limits


class ExecutionError(Exception):
    def __init__(self, result: ValidationLevelResult) -> None:
        super().__init__(result.message)
        self.result = result


def failed(message: str, hint: str | None = None) -> ExecutionError:
    return ExecutionError(
        ValidationLevelResult(level=5, name="execution", passed=False, message=message, hint=hint)
    )


def to_json(value: Any) -> Any:
    """Значения PostgreSQL → JSON. Числа остаются числами, чтобы их можно было рисовать."""
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            return value if value == value and abs(value) != float("inf") else str(value)
        case Decimal():
            return int(value) if value == value.to_integral_value() else float(value)
        case datetime() | date() | dtime():
            return value.isoformat()
        case timedelta():
            return str(value)
        case uuid.UUID():
            return str(value)
        case bytes() | bytearray() | memoryview():
            return f"<binary {len(value)} bytes>"
        case list() | tuple():
            return [to_json(v) for v in value]
        case dict():
            return {str(k): to_json(v) for k, v in value.items()}
        case _:
            return str(value)


async def execute_readonly(sql: str, conn: Conn, limits: Limits) -> QueryResult:
    """Выполняет SELECT; бросает ExecutionError с понятным сообщением для самокоррекции."""
    timeout = int(limits.statement_timeout_ms)
    tr = conn.transaction(readonly=True)
    await tr.start()
    started = time.perf_counter()
    try:
        await conn.execute(f"SET LOCAL statement_timeout = {timeout}")
        await conn.execute(f"SET LOCAL idle_in_transaction_session_timeout = {timeout}")
        stmt = await conn.prepare(sql)
        columns = [ColumnMeta(name=a.name, type=a.type.name) for a in stmt.get_attributes()]
        cursor = await stmt.cursor()
        records = await cursor.fetch(limits.max_rows + 1)
    except asyncpg.QueryCanceledError as e:
        raise failed(
            f"Превышено время выполнения ({timeout} мс)",
            hint="Упростите запрос: добавьте фильтры или агрегацию",
        ) from e
    except asyncpg.PostgresError as e:
        raise failed(f"Ошибка выполнения: {e}", hint=getattr(e, "hint", None)) from e
    finally:
        await tr.rollback()
    duration_ms = round((time.perf_counter() - started) * 1000)

    truncated = len(records) > limits.max_rows
    rows: list[list[Any]] = []
    size = 0
    for record in records[: limits.max_rows]:
        row = [to_json(v) for v in record.values()]
        size += len(json.dumps(row, ensure_ascii=False, default=str))
        if size > limits.max_result_bytes:
            truncated = True
            break
        rows.append(row)

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        duration_ms=duration_ms,
    )
