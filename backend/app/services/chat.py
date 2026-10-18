"""Поток одного хода диалога: события агента → SSE, сохранение ответа и журнала запросов."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import structlog
from fastapi import status
from fastapi.sse import format_sse_event
from sqlalchemy import func, update

from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.models import ChatSession, Message, MessageRole, QueryLog, QueryStatus
from app.schemas.agent import (
    AgentEvent,
    AnswerEvent,
    ChartSpec,
    ClarificationRequest,
    DoneEvent,
    ErrorEvent,
    QueryResult,
    SqlEvent,
    ValidationLevelResult,
    ValidationReport,
)

log = structlog.get_logger()

# Один активный поток на сессию: повторная отправка во время ответа → 409
_active_sessions: set[uuid.UUID] = set()


def acquire_session(session_id: uuid.UUID) -> None:
    if session_id in _active_sessions:
        raise AppError(
            status.HTTP_409_CONFLICT, "session_busy", "Агент ещё отвечает на предыдущий вопрос"
        )
    _active_sessions.add(session_id)


def release_session(session_id: uuid.UUID) -> None:
    _active_sessions.discard(session_id)


@dataclass
class TurnAccumulator:
    """Собирает итог хода из событий, чтобы сохранить его как сообщение ассистента."""

    sql: str | None = None
    levels: list[ValidationLevelResult] = field(default_factory=list)
    result: QueryResult | None = None
    answer: list[str] = field(default_factory=list)
    chart: ChartSpec | None = None
    clarification: ClarificationRequest | None = None
    error: ErrorEvent | None = None

    def add(self, e: AgentEvent) -> None:
        match e.data:
            case SqlEvent(sql=sql):
                self.sql, self.levels, self.result = sql, [], None  # новая попытка
            case ValidationLevelResult():
                self.levels.append(e.data)
            case QueryResult():
                self.result = e.data
            case AnswerEvent(text=text):
                self.answer.append(text)
            case ChartSpec():
                self.chart = e.data
            case ClarificationRequest():
                self.clarification = e.data
            case ErrorEvent():
                self.error = e.data

    def content(self) -> str:
        if self.answer:
            return "".join(self.answer)
        if self.clarification:
            return self.clarification.question
        if self.error:
            return self.error.message
        return ""

    def report(self) -> ValidationReport | None:
        if not self.levels:
            return None
        return ValidationReport(passed=all(lv.passed for lv in self.levels), levels=self.levels)

    def query_log(self, session_id: uuid.UUID) -> QueryLog | None:
        if self.sql is None:
            return None
        blocked = next((lv for lv in self.levels if not lv.passed), None)
        if self.result is not None:
            query_status, level = QueryStatus.OK, None
        elif blocked is not None and blocked.level < 5:
            query_status, level = QueryStatus.BLOCKED, blocked.level
        else:
            query_status, level = QueryStatus.ERROR, None
        return QueryLog(
            session_id=session_id,
            sql=self.sql,
            status=query_status,
            blocked_level=level,
            duration_ms=self.result.duration_ms if self.result else None,
            row_count=self.result.row_count if self.result else None,
        )


def sse(e: AgentEvent) -> bytes:
    return format_sse_event(event=e.type, data_str=e.data.model_dump_json())


async def save_turn(session_id: uuid.UUID, acc: TurnAccumulator, trace_id: str | None) -> uuid.UUID:
    async with get_sessionmaker()() as db:
        message = Message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=acc.content(),
            sql=acc.sql,
            validation_report=(r.model_dump(mode="json") if (r := acc.report()) else None),
            result_meta=acc.result.model_dump(mode="json") if acc.result else None,
            chart_spec=acc.chart.model_dump(mode="json") if acc.chart else None,
            clarification=(
                acc.clarification.model_dump(mode="json") if acc.clarification else None
            ),
            trace_id=trace_id,
        )
        db.add(message)
        if (entry := acc.query_log(session_id)) is not None:
            db.add(entry)
        await db.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now())
        )
        await db.commit()
        return message.id


async def stream_turn(
    session_id: uuid.UUID, events: AsyncIterator[AgentEvent]
) -> AsyncIterator[bytes]:
    """Пересылает события агента, сохраняет ответ и подставляет message_id в `done`.

    Сессия уже захвачена (acquire_session) вызывающим кодом и освобождается здесь.
    """
    acc = TurnAccumulator()
    done = DoneEvent()
    try:
        try:
            async for e in events:
                if isinstance(e.data, DoneEvent):
                    done = e.data
                    break
                acc.add(e)
                yield sse(e)
        except Exception as exc:  # агент упал — пользователь получает ошибку, а не обрыв
            log.exception("agent_failed", session_id=str(session_id), exc_info=exc)
            error = AgentEvent(
                type="error",
                data=ErrorEvent(code="internal_error", message="Агент завершился с ошибкой"),
            )
            acc.add(error)
            yield sse(error)

        message_id = await save_turn(session_id, acc, done.trace_id)
        done.message_id = str(message_id)
        yield sse(AgentEvent(type="done", data=done))
    finally:
        # срабатывает и при обрыве соединения клиентом (генератор отменяется)
        release_session(session_id)
