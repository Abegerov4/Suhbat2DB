"""Сложность вопроса Spider: перенос eval_hardness из официального evaluation.py.

В dev.json Spider нет поля сложности — его вычисляет скрипт оценки по разобранному SQL
(поле "sql"). Логика, включая особенности оригинала, сохранена без изменений, чтобы
уровни совпадали с публикуемыми в литературе (easy / medium / hard / extra).
"""

from typing import Any

WHERE_OPS = ("not", "between", "=", ">", "<", ">=", "<=", "!=", "in", "like", "is", "exists")
AGG_NONE = 0


def has_agg(unit: Any) -> bool:
    return bool(unit[0] != AGG_NONE)


def count_agg(units: list[Any]) -> int:
    return len([u for u in units if has_agg(u)])


def get_nested(sql: dict[str, Any]) -> list[dict[str, Any]]:
    nested = []
    for cond in sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]:
        if isinstance(cond[3], dict):
            nested.append(cond[3])
        if isinstance(cond[4], dict):
            nested.append(cond[4])
    for key in ("intersect", "except", "union"):
        if sql[key] is not None:
            nested.append(sql[key])
    return nested


def count_component1(sql: dict[str, Any]) -> int:
    count = 0
    if sql["where"]:
        count += 1
    if sql["groupBy"]:
        count += 1
    if sql["orderBy"]:
        count += 1
    if sql["limit"] is not None:
        count += 1
    if sql["from"]["table_units"]:  # JOIN
        count += len(sql["from"]["table_units"]) - 1
    ao = sql["from"]["conds"][1::2] + sql["where"][1::2] + sql["having"][1::2]
    count += len([t for t in ao if t == "or"])
    conds = sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]
    count += len([c for c in conds if c[1] == WHERE_OPS.index("like")])
    return count


def count_others(sql: dict[str, Any]) -> int:
    count = 0
    agg = count_agg(sql["select"][1])
    agg += count_agg(sql["where"][::2])
    agg += count_agg(sql["groupBy"])
    if sql["orderBy"]:
        agg += count_agg(
            [u[1] for u in sql["orderBy"][1] if u[1]] + [u[2] for u in sql["orderBy"][1] if u[2]]
        )
    agg += count_agg(sql["having"])
    if agg > 1:
        count += 1
    if len(sql["select"][1]) > 1:
        count += 1
    if len(sql["where"]) > 1:
        count += 1
    if len(sql["groupBy"]) > 1:
        count += 1
    return count


def hardness(sql: dict[str, Any]) -> str:
    c1, c2, others = count_component1(sql), len(get_nested(sql)), count_others(sql)
    if c1 <= 1 and others == 0 and c2 == 0:
        return "easy"
    if (others <= 2 and c1 <= 1 and c2 == 0) or (c1 <= 2 and others < 2 and c2 == 0):
        return "medium"
    if (
        (others > 2 and c1 <= 2 and c2 == 0)
        or (2 < c1 <= 3 and others <= 2 and c2 == 0)
        or (c1 <= 1 and others == 0 and c2 <= 1)
    ):
        return "hard"
    return "extra"
