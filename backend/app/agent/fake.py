"""Заглушка агента: детерминированные события по CONTRACTS §2 без LLM и без БД.

Сценарии (по тексту вопроса):
- «удали», «измени», «drop», «delete» … → отказ на guard_input;
- «продаж» → уточнение (показатель и тип квартала), затем ответ после resume;
- всё остальное → сразу ответ с SQL, отчётом валидатора, таблицей и графиком.
"""

import asyncio
from collections.abc import AsyncIterator

from pydantic import BaseModel

from app.agent.runner import RunContext
from app.schemas.agent import (
    AgentEvent,
    Ambiguity,
    AnswerEvent,
    ChartSpec,
    ClarificationAnswer,
    ClarificationOption,
    ClarificationRequest,
    ColumnMeta,
    DoneEvent,
    ErrorEvent,
    EventType,
    NodeName,
    QueryResult,
    SqlEvent,
    StepEvent,
    ValidationLevelResult,
)

DANGEROUS_WORDS = ("удали", "удалить", "измени", "изменить", "drop", "delete", "update", "insert")

FAKE_SQL = """SELECT r.name AS region, sum(o.total_amount) AS revenue
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
JOIN cities AS ci ON ci.id = c.city_id
JOIN regions AS r ON r.id = ci.region_id
WHERE o.status <> 'cancelled'
  AND o.created_at >= '2026-07-01' AND o.created_at < '2026-10-01'
GROUP BY r.name
ORDER BY revenue DESC
LIMIT 1000"""

FAKE_RESULT = QueryResult(
    columns=[ColumnMeta(name="region", type="text"), ColumnMeta(name="revenue", type="numeric")],
    rows=[
        ["Алматы", 1489214330],
        ["Астана", 1192873110],
        ["Шымкент", 597412920],
        ["Карагандинская область", 534118870],
        ["Актюбинская область", 296045130],
    ],
    row_count=5,
    truncated=False,
    duration_ms=42,
)

FAKE_CLARIFICATION = ClarificationRequest(
    question="Уточните, пожалуйста, что именно посчитать:",
    ambiguities=[
        Ambiguity(
            id="metric",
            type="metric",
            span="продажи",
            options=[
                ClarificationOption(
                    id="revenue", label="Выручка", description="sum(orders.total_amount)"
                ),
                ClarificationOption(
                    id="orders", label="Количество заказов", description="count(orders.id)"
                ),
                ClarificationOption(
                    id="units", label="Проданные единицы", description="sum(order_items.quantity)"
                ),
            ],
        ),
        Ambiguity(
            id="quarter",
            type="temporal",
            span="квартал",
            options=[
                ClarificationOption(id="calendar", label="Календарный квартал"),
                ClarificationOption(
                    id="fiscal", label="Финансовый квартал", description="год начинается 1 апреля"
                ),
            ],
        ),
    ],
)

VALIDATION_LEVELS = [
    ValidationLevelResult(level=1, name="syntax", passed=True, message="Синтаксис корректен"),
    ValidationLevelResult(level=2, name="readonly_policy", passed=True, message="Только SELECT"),
    ValidationLevelResult(
        level=3, name="schema", passed=True, message="Все таблицы и столбцы существуют"
    ),
    ValidationLevelResult(
        level=4, name="explain", passed=True, message="Оценка стоимости в пределах лимита"
    ),
    ValidationLevelResult(level=5, name="execution", passed=True, message="Выполнено за 42 мс"),
]
PRE_NODES: tuple[NodeName, ...] = ("guard_input", "schema_linking", "detect_ambiguity")


def event(type_: EventType, data: BaseModel) -> AgentEvent:
    return AgentEvent(type=type_, data=data)


class FakeAgentRunner:
    def __init__(self, delay: float = 0.2) -> None:
        self.delay = delay

    async def _pause(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)

    async def _step(self, node: NodeName, detail: str | None = None) -> AsyncIterator[AgentEvent]:
        yield event("step", StepEvent(node=node, status="started"))
        await self._pause()
        yield event("step", StepEvent(node=node, status="finished", detail=detail))

    async def run(self, ctx: RunContext, question: str) -> AsyncIterator[AgentEvent]:
        text = question.lower()
        if any(word in text for word in DANGEROUS_WORDS):
            async for e in self._step("guard_input", "Запрос на изменение данных"):
                yield e
            yield event(
                "error",
                ErrorEvent(
                    code="refused",
                    message="Я могу только читать данные: изменение и удаление недоступны.",
                ),
            )
            yield event("done", DoneEvent())
            return

        for node in PRE_NODES:
            async for e in self._step(node):
                yield e

        if "продаж" in text:
            yield event("clarification", FAKE_CLARIFICATION)
            yield event("done", DoneEvent(awaiting_clarification=True))
            return

        async for e in self._answer(note=None):
            yield e

    async def resume(
        self,
        ctx: RunContext,
        clarification: ClarificationRequest,
        answers: list[ClarificationAnswer],
    ) -> AsyncIterator[AgentEvent]:
        labels = []
        for answer in answers:
            ambiguity = next(a for a in clarification.ambiguities if a.id == answer.ambiguity_id)
            option = next((o for o in ambiguity.options if o.id == answer.option_id), None)
            labels.append(option.label if option else answer.free_text or "")
        async for e in self._answer(note="Учтено уточнение: " + ", ".join(labels) + "."):
            yield e

    async def _answer(self, note: str | None) -> AsyncIterator[AgentEvent]:
        async for e in self._step("generate_sql"):
            yield e
        yield event("sql", SqlEvent(sql=FAKE_SQL, attempt=1))

        yield event("step", StepEvent(node="validate_sql", status="started"))
        for result in VALIDATION_LEVELS[:4]:
            await self._pause()
            yield event("validation", result)
        yield event("step", StepEvent(node="validate_sql", status="finished"))

        async for e in self._step("execute"):
            yield e
        yield event("validation", VALIDATION_LEVELS[4])
        yield event("result", FAKE_RESULT)

        yield event("step", StepEvent(node="explain_and_visualize", status="started"))
        chunks = [
            "Это демонстрационный ответ заглушки агента. ",
            "Больше всего выручки в прошлом квартале принёс Алматы — 1,49 млрд ₸, ",
            "на втором месте Астана — 1,19 млрд ₸.",
        ]
        if note:
            chunks.insert(0, note + " ")
        for chunk in chunks:
            await self._pause()
            yield event("answer", AnswerEvent(text=chunk))
        yield event(
            "chart", ChartSpec(type="bar", x="region", y=["revenue"], title="Выручка по регионам")
        )
        yield event("step", StepEvent(node="explain_and_visualize", status="finished"))
        yield event("done", DoneEvent())
