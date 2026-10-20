"""Метрики evals: execution accuracy, неоднозначность, безопасность, статистика.

EX: результаты сравниваются как мультимножества строк (порядок — только если в эталоне
есть ORDER BY), числа с допуском 1e-6, порядок столбцов может отличаться (как в
test-suite оценке Spider): «SELECT name, age» и «SELECT age, name» — один ответ.
"""

import math
import random
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal
from itertools import combinations, permutations
from typing import Any

from sqlglot import exp, parse_one

Row = Sequence[Any]
MAX_PERMUTED_COLUMNS = 6


def norm(value: Any) -> Any:
    """Значение для сравнения: числа с допуском 1e-6, даты — ISO-строкой, текст без пробелов."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        f = float(value)
        if math.isnan(f):
            return "nan"
        return round(f, 6) + 0.0  # -0.0 → 0.0
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    text = str(value).strip()
    try:  # «12.50» из text-столбца и 12.5 из numeric — одно число
        return round(float(text), 6) + 0.0 if text and text[0] in "-0123456789." else text
    except ValueError:
        return text


def _rows(rows: Sequence[Row], order: Sequence[int] | None = None) -> list[tuple[Any, ...]]:
    if order is None:
        return [tuple(norm(v) for v in r) for r in rows]
    return [tuple(norm(r[i]) for i in order) for r in rows]


def results_equal(gold: Sequence[Row], pred: Sequence[Row], ordered: bool) -> bool:
    if len(gold) != len(pred):
        return False
    if not gold:
        return True
    width = len(gold[0])
    if any(len(r) != width for r in pred):
        return False
    g = _rows(gold)
    orders: list[Sequence[int] | None] = [None]
    if 1 < width <= MAX_PERMUTED_COLUMNS:
        orders += list(permutations(range(width)))[1:]
    for order in orders:
        p = _rows(pred, order)
        if (g == p) if ordered else (Counter(g) == Counter(p)):
            return True
    return False


def results_equal_relaxed(gold: Sequence[Row], pred: Sequence[Row], ordered: bool) -> bool:
    """Ослабленный EX: в ответе могут быть лишние столбцы, если среди них есть все эталонные.

    Агент часто добавляет полезный контекст (например, число заказов к сумме) — строгий EX
    считает это ошибкой. Основная метрика — строгий EX, ослабленный приводится рядом.
    """
    if results_equal(gold, pred, ordered):
        return True
    if not gold or not pred or len(gold) != len(pred):
        return False
    gw, pw = len(gold[0]), len(pred[0])
    if pw <= gw or pw > 8:
        return False
    for cols in combinations(range(pw), gw):
        projected = [tuple(r[i] for i in cols) for r in pred]
        if results_equal(gold, projected, ordered):
            return True
    return False


def has_order_by(sql: str, dialect: str = "postgres") -> bool:
    """Порядок важен, если внешний запрос эталона сортирует результат."""
    try:
        tree = parse_one(sql, dialect=dialect)
    except Exception:
        return "order by" in sql.lower()
    return tree.args.get("order") is not None if isinstance(tree, exp.Query) else False


def gold_tables(sql: str) -> set[str]:
    """Таблицы эталонного SQL (без CTE) — для schema recall."""
    try:
        tree = parse_one(sql, dialect="postgres")
    except Exception:
        return set()
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    return {t.name.lower() for t in tree.find_all(exp.Table) if t.name.lower() not in ctes}


# --- Классификация -------------------------------------------------------------------------


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


# --- Статистика ----------------------------------------------------------------------------


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float | int]:
    """Точный тест Макнемара для парных бинарных исходов (EX системы A и B на тех же вопросах).

    b01 — A ошиблась, B верно; b10 — наоборот. p — двусторонний биномиальный тест по
    расхождениям (точный вариант корректнее χ² при малом числе расхождений).
    """
    assert len(a) == len(b)
    b01 = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    b10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    n = b01 + b10
    if n == 0:
        return {"b01": 0, "b10": 0, "p_value": 1.0}
    k = min(b01, b10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return {"b01": b01, "b10": b10, "p_value": round(min(1.0, 2 * tail), 4)}


def bootstrap_ci(
    values: Sequence[float], iterations: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    """95% перцентильный bootstrap-интервал среднего."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(iterations))
    lo = means[int(alpha / 2 * iterations)]
    hi = means[min(iterations - 1, int((1 - alpha / 2) * iterations))]
    return (round(lo, 4), round(hi, 4))


def paired_bootstrap_diff(
    a: Sequence[float], b: Sequence[float], iterations: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """95% интервал разности средних B − A на тех же вопросах (парный bootstrap)."""
    assert len(a) == len(b)
    if not a:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(iterations):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(b[i] - a[i] for i in idx) / n)
    diffs.sort()
    return (round(diffs[int(0.025 * iterations)], 4), round(diffs[int(0.975 * iterations)], 4))


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def cohen_kappa(a: Sequence[Any], b: Sequence[Any]) -> float:
    """Согласованность двух разметчиков (для проверки разметки ambiguous_ru)."""
    assert len(a) == len(b) and a
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    return 1.0 if expected == 1 else round((observed - expected) / (1 - expected), 3)
