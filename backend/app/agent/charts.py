"""Выбор графика по типам столбцов результата — кодом, а не LLM (дёшево и предсказуемо)."""

from app.schemas.agent import ChartSpec, QueryResult

NUMERIC = {"int2", "int4", "int8", "numeric", "float4", "float8", "money"}
TEMPORAL = {"date", "timestamp", "timestamptz"}


def choose_chart(result: QueryResult, title: str | None = None) -> ChartSpec | None:
    if result.row_count < 2 or len(result.columns) < 2:
        return None  # одно число или одна колонка — график не нужен
    numeric = [c.name for c in result.columns if c.type in NUMERIC]
    temporal = [c.name for c in result.columns if c.type in TEMPORAL]
    labels = [c.name for c in result.columns if c.type not in NUMERIC]
    if not numeric:
        return None
    if temporal:
        y = [c for c in numeric if c != temporal[0]][:3]
        return ChartSpec(type="line", x=temporal[0], y=y, title=title) if y else None
    if not labels:
        if len(numeric) >= 2:
            return ChartSpec(type="scatter", x=numeric[0], y=[numeric[1]], title=title)
        return None
    if result.row_count > 30:
        return None  # столбчатая диаграмма из сотен категорий нечитаема
    y = numeric[:3]
    if len(y) == 1 and 2 <= result.row_count <= 6 and _all_positive(result, y[0]):
        return ChartSpec(type="pie", x=labels[0], y=y, title=title)
    return ChartSpec(type="bar", x=labels[0], y=y, title=title)


def _all_positive(result: QueryResult, column: str) -> bool:
    index = [c.name for c in result.columns].index(column)
    return all(isinstance(r[index], int | float) and r[index] > 0 for r in result.rows)
