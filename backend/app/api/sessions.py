import uuid
from typing import Any

from fastapi import APIRouter, Response, status
from fastapi.sse import EventSourceResponse
from sqlalchemy import select

from app.agent.runner import RunContext
from app.api.deps import CurrentUser, DbSession, Runner
from app.core.errors import AppError, not_found
from app.models import ChatSession, Datasource, DatasourceStatus, Message, MessageRole, User
from app.schemas.agent import ChartSpec, ClarificationRequest, ErrorEvent, QueryResult
from app.schemas.api import ClarifyRequest, MessageCreate, MessageOut, SessionCreate, SessionOut
from app.services.chat import acquire_session, stop_turn, stream_turn

router = APIRouter(prefix="/sessions", tags=["sessions"])

DEFAULT_TITLE = "Новый диалог"
CLARIFICATION_PREFIX = "Уточнение: "  # ответ на уточнение — не новый вопрос (учёт в /stats)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
# Ответ возвращается вручную (не генератор-endpoint): проверки выше отдают обычные HTTP-ошибки
SSE_DOC: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Поток событий агента (CONTRACTS §2)",
        "content": {"text/event-stream": {}},
    }
}


async def own_session(db: DbSession, session_id: uuid.UUID, user: User) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:  # чужие сессии не раскрываются
        raise not_found("session")
    return session


def to_message_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        created_at=m.created_at,
        sql=m.sql,
        validation_report=m.validation_report,
        result=QueryResult.model_validate(m.result_meta) if m.result_meta else None,
        chart_spec=ChartSpec.model_validate(m.chart_spec) if m.chart_spec else None,
        clarification=(
            ClarificationRequest.model_validate(m.clarification) if m.clarification else None
        ),
        error=ErrorEvent.model_validate(m.error) if m.error else None,
        trace_id=m.trace_id,
    )


@router.get("")
async def list_sessions(db: DbSession, user: CurrentUser) -> list[SessionOut]:
    rows = await db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    return [SessionOut.model_validate(s) for s in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, db: DbSession, user: CurrentUser) -> SessionOut:
    datasource = await db.get(Datasource, body.datasource_id)
    if datasource is None:
        raise not_found("datasource")
    session = ChatSession(
        user_id=user.id, datasource_id=datasource.id, title=body.title or DEFAULT_TITLE
    )
    db.add(session)
    await db.commit()
    return SessionOut.model_validate(session)


@router.get("/{session_id}/messages")
async def list_messages(
    session_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[MessageOut]:
    await own_session(db, session_id, user)
    rows = await db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return [to_message_out(m) for m in rows]


@router.post("/{session_id}/messages", responses=SSE_DOC)
async def send_message(
    session_id: uuid.UUID, body: MessageCreate, db: DbSession, user: CurrentUser, runner: Runner
) -> EventSourceResponse:
    session = await own_session(db, session_id, user)
    datasource = await db.get(Datasource, session.datasource_id)
    if datasource is None or datasource.status != DatasourceStatus.READY:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "datasource_not_ready",
            "Источник данных ещё индексируется или недоступен",
        )
    if await pending_clarification(db, session_id) is not None:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "clarification_pending",
            "Сначала ответьте на уточняющий вопрос (POST /clarify)",
        )

    acquire_session(session_id)
    question = body.content.strip()
    db.add(Message(session_id=session_id, role=MessageRole.USER, content=question))
    if session.title == DEFAULT_TITLE:
        session.title = question[:80]
    await db.commit()

    ctx = RunContext(session_id=session_id, datasource_id=datasource.id, user_id=user.id)
    return EventSourceResponse(
        stream_turn(session_id, runner.run(ctx, question)), headers=SSE_HEADERS
    )


async def pending_clarification(
    db: DbSession, session_id: uuid.UUID
) -> ClarificationRequest | None:
    """Уточнение ожидает ответа, если последнее сообщение — вопрос агента."""
    last = await db.scalar(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if last is None or last.role != MessageRole.ASSISTANT or last.clarification is None:
        return None
    return ClarificationRequest.model_validate(last.clarification)


@router.post("/{session_id}/clarify", responses=SSE_DOC)
async def clarify(
    session_id: uuid.UUID, body: ClarifyRequest, db: DbSession, user: CurrentUser, runner: Runner
) -> EventSourceResponse:
    session = await own_session(db, session_id, user)
    clarification = await pending_clarification(db, session_id)
    if clarification is None:
        raise AppError(
            status.HTTP_409_CONFLICT, "no_pending_clarification", "Нет вопроса, ожидающего ответа"
        )

    ambiguities = {a.id: a for a in clarification.ambiguities}
    parts = []
    for answer in body.answers:
        ambiguity = ambiguities.get(answer.ambiguity_id)
        option = (
            next((o for o in ambiguity.options if o.id == answer.option_id), None)
            if ambiguity
            else None
        )
        if ambiguity is None or (option is None and not (answer.free_text or "").strip()):
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_clarification",
                f"Некорректный ответ на уточнение «{answer.ambiguity_id}»",
            )
        parts.append(f"{ambiguity.span} → {option.label if option else answer.free_text}")

    acquire_session(session_id)
    db.add(
        Message(
            session_id=session_id,
            role=MessageRole.USER,
            content=CLARIFICATION_PREFIX + "; ".join(parts),
        )
    )
    await db.commit()

    ctx = RunContext(session_id=session_id, datasource_id=session.datasource_id, user_id=user.id)
    return EventSourceResponse(
        stream_turn(session_id, runner.resume(ctx, clarification, body.answers)),
        headers=SSE_HEADERS,
    )


@router.post("/{session_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    """Остановить ответ агента. Поток завершится событиями error (cancelled) и done.

    Обрыв соединения ход не останавливает: ответ дописывается и сохраняется.
    """
    await own_session(db, session_id, user)
    stop_turn(session_id)  # повторный вызов и вызов без активного хода — не ошибка
    return Response(status_code=status.HTTP_204_NO_CONTENT)
