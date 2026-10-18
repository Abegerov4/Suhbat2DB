from typing import Any

import pytest

from app.agent.charts import choose_chart
from app.agent.nodes import ungrounded_numbers
from app.schemas.agent import ColumnMeta, QueryResult


def result(columns: list[tuple[str, str]], rows: list[list[Any]]) -> QueryResult:
    return QueryResult(
        columns=[ColumnMeta(name=n, type=t) for n, t in columns],
        rows=rows,
        row_count=len(rows),
        truncated=False,
        duration_ms=1,
    )


@pytest.mark.parametrize(
    ("columns", "rows", "expected"),
    [
        ([("n", "int8")], [[1]], None),  # одно число
        (
            [("month", "date"), ("revenue", "numeric")],
            [["2026-01-01", 1], ["2026-02-01", 2]],
            "line",
        ),
        ([("region", "text"), ("revenue", "numeric")], [["A", 1], ["B", 2], ["C", 3]], "pie"),
        ([("region", "text"), ("revenue", "numeric")], [[str(i), i] for i in range(1, 10)], "bar"),
        ([("region", "text"), ("delta", "numeric")], [["A", -1], ["B", 2]], "bar"),
        ([("region", "text"), ("revenue", "numeric")], [[str(i), i] for i in range(40)], None),
        ([("name", "text"), ("city", "text")], [["a", "b"], ["c", "d"]], None),
        ([("price", "numeric"), ("cost", "numeric")], [[1, 2], [3, 4]], "scatter"),
        ([("x", "int4")], [[1], [2]], None),
    ],
)
def test_choose_chart(
    columns: list[tuple[str, str]], rows: list[list[Any]], expected: str | None
) -> None:
    chart = choose_chart(result(columns, rows))
    assert (chart.type if chart else None) == expected


def test_ungrounded_numbers() -> None:
    r = result([("region", "text"), ("revenue", "numeric")], [["A", 1489214330], ["B", 12.5]])
    assert ungrounded_numbers("Выручка 1 489 214 330 ₸", r) == []
    assert ungrounded_numbers("Выручка 9 999 999 ₸", r) == ["9999999"]
