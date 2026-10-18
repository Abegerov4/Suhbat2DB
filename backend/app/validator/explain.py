"""Уровень 4: план выполнения (EXPLAIN без ANALYZE — запрос не выполняется)."""

import json
from typing import Any

import asyncpg

from app.schemas.agent import ValidationLevelResult
from app.services.target_db import Conn
from app.validator.limits import Limits


def result(passed: bool, message: str, hint: str | None = None) -> ValidationLevelResult:
    return ValidationLevelResult(level=4, name="explain", passed=passed, message=message, hint=hint)


def walk(plan: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [plan]
    for child in plan.get("Plans", []):
        nodes.extend(walk(child))
    return nodes


def has_condition(plan: dict[str, Any]) -> bool:
    """Есть ли у узла (или его потомков-сканов) условие, связывающее его с внешней стороной."""
    return any(
        key in node
        for node in walk(plan)
        for key in ("Index Cond", "Recheck Cond", "Join Filter", "Hash Cond", "Merge Cond")
    )


def cartesian_products(plan: dict[str, Any], min_rows: int) -> list[tuple[float, float]]:
    """Nested Loop без условия соединения, где обе стороны больше min_rows строк."""
    found = []
    for node in walk(plan):
        if node.get("Node Type") != "Nested Loop" or "Join Filter" in node:
            continue
        children = node.get("Plans", [])
        if len(children) != 2 or has_condition(children[1]):
            continue
        outer, inner = (float(c.get("Plan Rows", 0)) for c in children)
        if outer > min_rows and inner > min_rows:
            found.append((outer, inner))
    return found


async def explain(sql: str, conn: Conn, limits: Limits) -> ValidationLevelResult:
    tr = conn.transaction(readonly=True)
    await tr.start()
    try:
        await conn.execute(f"SET LOCAL statement_timeout = {int(limits.statement_timeout_ms)}")
        raw = await conn.fetchval(f"EXPLAIN (FORMAT JSON) {sql}")
    except asyncpg.PostgresError as e:
        return result(False, f"Ошибка планировщика: {e}", hint=getattr(e, "hint", None))
    finally:
        await tr.rollback()

    plan = (json.loads(raw) if isinstance(raw, str) else raw)[0]["Plan"]
    cost = float(plan["Total Cost"])

    products = cartesian_products(plan, limits.cartesian_min_rows)
    if products:
        outer, inner = products[0]
        return result(
            False,
            f"Декартово произведение: соединение {outer:,.0f} × {inner:,.0f} строк без условия",
            hint="Проверьте условия JOIN … ON: каждая таблица должна быть связана ключом",
        )
    if cost > limits.max_explain_cost:
        return result(
            False,
            f"Запрос слишком тяжёлый: оценка стоимости {cost:,.0f} "
            f"> {limits.max_explain_cost:,.0f}",
            hint="Добавьте фильтры (например, по дате) или агрегируйте данные",
        )
    return result(True, f"Оценка стоимости {cost:,.0f}, ожидается строк: {plan['Plan Rows']}")
