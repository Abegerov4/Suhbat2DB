"""Состояние графа (CONTRACTS §5) и контекст прогона.

Поля без reducer перезаписываются каждым ходом диалога; clarifications и history
накапливаются в пределах сессии (thread_id = id чата) и хранятся в checkpoint'ах.
"""

from dataclasses import dataclass, field
from datetime import date
from operator import add
from typing import Annotated, Any, TypedDict

from asyncpg import Pool

from app.schemas.schema_snapshot import SchemaSnapshot
from app.validator import Limits


class Feedback(TypedDict):
    """Ошибка предыдущей попытки — передаётся генератору при самокоррекции."""

    sql: str
    level: int
    message: str
    hint: str | None


class Clarification(TypedDict):
    span: str
    choice: str  # что выбрал пользователь (метка или свой текст)
    interpretation: str  # трактовка для генератора SQL


class Turn(TypedDict):
    question: str
    sql: str | None
    answer: str | None


class AgentState(TypedDict, total=False):
    question: str
    resolved_question: str
    route: str
    # уточнения
    pending_clarification: dict[str, Any] | None
    turn_clarifications: list[Clarification]
    clarification_rounds: int
    clarifications: Annotated[list[Clarification], add]  # память сессии
    # schema linking
    linked_schema: str
    linked_tables: list[str]
    examples: list[dict[str, str]]
    # генерация и проверка
    sql: str | None
    attempts: int
    feedback: list[Feedback]
    normalized_sql: str | None
    result: dict[str, Any] | None
    answer: str | None
    chart: dict[str, Any] | None
    error: dict[str, str] | None
    history: Annotated[list[Turn], add]


def new_turn(question: str) -> AgentState:
    """Начальные значения полей одного хода (поля сессии не трогаются)."""
    return AgentState(
        question=question,
        resolved_question=question,
        route="",
        pending_clarification=None,
        turn_clarifications=[],
        clarification_rounds=0,
        linked_schema="",
        linked_tables=[],
        examples=[],
        sql=None,
        attempts=0,
        feedback=[],
        normalized_sql=None,
        result=None,
        answer=None,
        chart=None,
        error=None,
    )


@dataclass
class AgentContext:
    """Не сохраняется в checkpoint: снимок схемы и соединения берутся заново на каждый ход."""

    snapshot: SchemaSnapshot
    pool: Pool | None
    limits: Limits = field(default_factory=Limits)
    today: date = field(default_factory=date.today)
