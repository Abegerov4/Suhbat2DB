"""Schema linking: какие таблицы, столбцы и значения нужны для ответа на вопрос.

1. Гибридный поиск по документам схемы (dense + BM25, RRF).
2. Таблицы ранжируются по сумме обратных рангов их документов (таблица, столбцы, значения).
3. Берутся top-N таблиц; каждая связывается с главной (первой по score) по всем кратчайшим
   путям графа внешних ключей — добавляются промежуточные таблицы для JOIN.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.agent.retrieval.store import Hit, SchemaStore, SearchMode
from app.schemas.schema_snapshot import SchemaSnapshot, TableInfo

TableKey = tuple[str, str]
RRF_K = 60
MAX_VALUES_PER_COLUMN = 12


@dataclass
class LinkedSchema:
    tables: list[TableInfo]
    timezone: str | None = None
    # (таблица, столбец) → значения, найденные по вопросу (value linking)
    matched_values: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    added_for_joins: list[str] = field(default_factory=list)

    @property
    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]

    def render(self) -> str:
        """Компактное DDL-подобное описание для промпта (Just-in-Time context)."""
        lines = [f"-- PostgreSQL, часовой пояс БД: {self.timezone or 'UTC'}"]
        for t in self.tables:
            rows = f", ≈{t.row_estimate:,} строк".replace(",", " ")
            lines.append(f"\n-- {t.comment or ''}{rows}")
            lines.append(f"TABLE {t.schema_name}.{t.name} (")
            for c in t.columns:
                parts = [f"  {c.name} {c.data_type}"]
                if c.is_pk:
                    parts.append("PRIMARY KEY")
                if c.fk:
                    parts.append(f"REFERENCES {c.fk.rsplit('.', 1)[0]}({c.fk.rsplit('.', 1)[1]})")
                line = " ".join(parts)
                if c.comment:
                    line += f"  -- {c.comment}"
                values = self.matched_values.get((t.name, c.name)) or c.sample_values
                if values:
                    shown = ", ".join(f"'{v}'" for v in values[:MAX_VALUES_PER_COLUMN])
                    more = " …" if len(values) > MAX_VALUES_PER_COLUMN else ""
                    line += f"  [значения: {shown}{more}]"
                lines.append(line)
            lines.append(")")
        return "\n".join(lines)


def full_schema(snapshot: SchemaSnapshot) -> LinkedSchema:
    """Вся схема без отбора — для baseline и эксперимента «полная схема против linking»."""
    return LinkedSchema(tables=list(snapshot.tables), timezone=snapshot.timezone)


def fk_graph(snapshot: SchemaSnapshot) -> dict[TableKey, set[TableKey]]:
    graph: dict[TableKey, set[TableKey]] = defaultdict(set)
    for t in snapshot.tables:
        for c in t.columns:
            if c.fk:
                schema, table, _ = c.fk.split(".", 2)
                a, b = (t.schema_name, t.name), (schema, table)
                graph[a].add(b)
                graph[b].add(a)
    return graph


def bridges(
    graph: dict[TableKey, set[TableKey]], start: TableKey, goal: TableKey, max_paths: int = 3
) -> set[TableKey]:
    """Промежуточные таблицы всех кратчайших путей по внешним ключам от start до goal.

    Путей одной длины может быть несколько, и они означают разное: заказы связаны
    с регионом и через клиента (customers → cities), и через менеджера (managers).
    Добавляются все — выбор трактовки остаётся генератору и детектору неоднозначности."""
    distance = {start: 0}
    parents: dict[TableKey, list[TableKey]] = defaultdict(list)
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, ()):
            if nxt not in distance:
                distance[nxt] = distance[node] + 1
                queue.append(nxt)
            if distance[nxt] == distance[node] + 1:
                parents[nxt].append(node)
    if goal not in distance:
        return set()

    result: set[TableKey] = set()
    paths = 0

    def walk(node: TableKey) -> None:
        nonlocal paths
        if paths >= max_paths:
            return
        if node == start:
            paths += 1
            return
        for parent in parents[node]:
            if parent != start:
                result.add(parent)
            walk(parent)

    walk(goal)
    return result


def rank_tables(hits: list[Hit]) -> dict[TableKey, float]:
    scores: dict[TableKey, float] = defaultdict(float)
    for rank, hit in enumerate(hits):
        weight = 1.0 if hit.doc.kind != "value" else 1.5  # совпадение значения — сильный сигнал
        scores[(hit.doc.schema, hit.doc.table)] += weight / (RRF_K + rank)
    return scores


class SchemaLinker:
    def __init__(
        self,
        store: SchemaStore,
        top_tables: int = 5,
        candidates: int = 40,
        mode: SearchMode = "hybrid",
    ) -> None:
        self.store = store
        self.top_tables = top_tables
        self.candidates = candidates
        self.mode = mode

    async def link(self, question: str, snapshot: SchemaSnapshot) -> LinkedSchema:
        hits = await self.store.search(snapshot.datasource_id, question, self.candidates, self.mode)
        scores = rank_tables(hits)
        selected = [k for k, _ in sorted(scores.items(), key=lambda kv: -kv[1])][: self.top_tables]

        graph = fk_graph(snapshot)
        anchor = selected[0] if selected else None
        included: list[TableKey] = list(selected)
        added: list[str] = []
        for key in selected[1:]:
            assert anchor is not None
            for bridge in sorted(bridges(graph, key, anchor)):
                if bridge not in included:
                    included.append(bridge)
                    added.append(bridge[1])

        matched: dict[tuple[str, str], list[str]] = defaultdict(list)
        for hit in hits[:10]:
            if hit.doc.kind == "value" and hit.doc.column and hit.doc.value:
                matched[(hit.doc.table, hit.doc.column)].append(hit.doc.value)

        by_key = {(t.schema_name, t.name): t for t in snapshot.tables}
        tables = [by_key[k] for k in included if k in by_key]
        # найденные значения — в начало списка, остальные примеры — следом
        for (table, column), values in matched.items():
            info = next(
                (c for t in tables if t.name == table for c in t.columns if c.name == column), None
            )
            if info and info.sample_values:
                rest = [v for v in info.sample_values if v not in values]
                matched[(table, column)] = values + rest
        return LinkedSchema(
            tables=tables,
            timezone=snapshot.timezone,
            matched_values=dict(matched),
            added_for_joins=added,
        )
