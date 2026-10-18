"""Модели событий агента и их полезной нагрузки (CONTRACTS §2–3).

Используются заглушкой агента (роль 3), валидатором (роль 4) и LangGraph-агентом (роль 5).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

NodeName = Literal[
    "guard_input",
    "schema_linking",
    "detect_ambiguity",
    "clarify",
    "generate_sql",
    "validate_sql",
    "self_correct",
    "execute",
    "explain_and_visualize",
    "refuse",
]

AmbiguityType = Literal["metric", "temporal", "value", "schema", "scope"]


class ClarificationOption(BaseModel):
    id: str
    label: str
    description: str | None = None


class Ambiguity(BaseModel):
    id: str
    type: AmbiguityType
    span: str
    options: list[ClarificationOption] = Field(min_length=2, max_length=4)


class ClarificationRequest(BaseModel):
    question: str
    ambiguities: list[Ambiguity] = Field(min_length=1)


class ClarificationAnswer(BaseModel):
    ambiguity_id: str
    option_id: str | None = None
    free_text: str | None = Field(default=None, max_length=500)


class ValidationLevelResult(BaseModel):
    level: Literal[1, 2, 3, 4, 5]
    name: Literal["syntax", "readonly_policy", "schema", "explain", "execution"]
    passed: bool
    message: str | None = None
    hint: str | None = None
    fatal: bool = False


class ValidationReport(BaseModel):
    passed: bool
    levels: list[ValidationLevelResult]
    normalized_sql: str | None = None


class ColumnMeta(BaseModel):
    name: str
    type: str


class QueryResult(BaseModel):
    columns: list[ColumnMeta]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: int


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie", "scatter", "none"]
    x: str
    y: list[str]
    title: str | None = None


# --- События потока ------------------------------------------------------------------------


class StepEvent(BaseModel):
    node: NodeName
    status: Literal["started", "finished"]
    detail: str | None = None


class SqlEvent(BaseModel):
    sql: str
    attempt: int


class AnswerEvent(BaseModel):
    text: str


class ErrorEvent(BaseModel):
    code: str
    message: str


class DoneEvent(BaseModel):
    message_id: str | None = None
    trace_id: str | None = None
    awaiting_clarification: bool = False


EventType = Literal[
    "step", "clarification", "sql", "validation", "result", "answer", "chart", "error", "done"
]

EVENT_PAYLOADS: dict[EventType, type[BaseModel]] = {
    "step": StepEvent,
    "clarification": ClarificationRequest,
    "sql": SqlEvent,
    "validation": ValidationLevelResult,
    "result": QueryResult,
    "answer": AnswerEvent,
    "chart": ChartSpec,
    "error": ErrorEvent,
    "done": DoneEvent,
}


class AgentEvent(BaseModel):
    """Одно событие SSE: `event: <type>` + `data: <payload JSON>`."""

    type: EventType
    data: BaseModel
