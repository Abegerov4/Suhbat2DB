"""Сводка по диалогам пользователя для страницы «Обзор» (CONTRACTS §1)."""

from datetime import date, datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query, status
from sqlalchemy import ColumnElement, Date, cast, func, select

from app.api.deps import CurrentUser, DbSession
from app.api.sessions import CLARIFICATION_PREFIX
from app.core.errors import AppError
from app.models import (
    ChatSession,
    Datasource,
    DatasourceStatus,
    Feedback,
    Message,
    MessageRole,
    QueryLog,
    QueryStatus,
)
from app.schemas.api import BlockedLevel, DailyActivity, StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


def present(column: Any) -> ColumnElement[bool]:
    """JSONB-поле заполнено. None сохраняется как JSON null, поэтому IS NOT NULL не подходит."""
    return func.jsonb_typeof(column) == "object"


LEVEL_NAMES = {1: "syntax", 2: "readonly_policy", 3: "schema", 4: "explain", 5: "execution"}


def zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            f"Неизвестный часовой пояс: {tz}",
        ) from e


@router.get("")
async def stats(
    db: DbSession,
    user: CurrentUser,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
    tz: Annotated[str, Query(max_length=64, description="IANA, например Asia/Almaty")] = "UTC",
) -> StatsOut:
    """Ходы диалога, исход проверки SQL, оценки и активность по дням — только свои сессии."""
    local_now = datetime.now(zone(tz))
    first_day = local_now.date() - timedelta(days=days - 1)
    own = select(ChatSession.id).where(ChatSession.user_id == user.id)

    turns = (
        await db.execute(
            select(
                func.count().filter(present(Message.result_meta)),
                func.count().filter(present(Message.clarification)),
                func.count().filter(present(Message.error)),
            ).where(Message.session_id.in_(own), Message.role == MessageRole.ASSISTANT)
        )
    ).one()
    questions = await db.scalar(
        select(func.count()).where(
            Message.session_id.in_(own),
            Message.role == MessageRole.USER,
            Message.content.not_like(CLARIFICATION_PREFIX + "%"),
        )
    )

    queries = (
        await db.execute(
            select(
                func.count().filter(QueryLog.status == QueryStatus.OK),
                func.count().filter(QueryLog.status == QueryStatus.BLOCKED),
                func.count().filter(QueryLog.status == QueryStatus.ERROR),
                func.avg(QueryLog.duration_ms),
            ).where(QueryLog.session_id.in_(own))
        )
    ).one()
    blocked = dict(
        (
            await db.execute(
                select(QueryLog.blocked_level, func.count())
                .where(QueryLog.session_id.in_(own), QueryLog.status == QueryStatus.BLOCKED)
                .group_by(QueryLog.blocked_level)
            )
        ).all()
    )

    feedback = (
        await db.execute(
            select(
                func.count().filter(Feedback.score == 1),
                func.count().filter(Feedback.score == -1),
            ).where(Feedback.user_id == user.id)
        )
    ).one()

    day = cast(func.timezone(tz, Message.created_at), Date)
    is_question = (Message.role == MessageRole.USER) & Message.content.not_like(
        CLARIFICATION_PREFIX + "%"
    )
    is_assistant = Message.role == MessageRole.ASSISTANT
    rows = await db.execute(
        select(
            day,
            func.count().filter(is_question),
            func.count().filter(is_assistant & present(Message.result_meta)),
            func.count().filter(is_assistant & present(Message.clarification)),
            func.count().filter(is_assistant & present(Message.error)),
        )
        .where(Message.session_id.in_(own), day >= first_day)
        .group_by(day)
    )
    by_day: dict[date, DailyActivity] = {
        d: DailyActivity(date=d, questions=q, answered=a, clarifications=c, refused=r)
        for d, q, a, c, r in rows.all()
    }
    activity = [
        by_day.get(d, DailyActivity(date=d))
        for d in (first_day + timedelta(days=i) for i in range(days))
    ]

    sessions = await db.scalar(select(func.count()).select_from(own.subquery()))
    datasources = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Datasource.status == DatasourceStatus.READY),
            )
        )
    ).one()
    return StatsOut(
        questions=questions or 0,
        answered=turns[0],
        clarifications=turns[1],
        refused=turns[2],
        sessions=sessions or 0,
        datasources=datasources[0],
        datasources_ready=datasources[1],
        queries_ok=queries[0],
        queries_blocked=queries[1],
        queries_failed=queries[2],
        avg_duration_ms=round(queries[3]) if queries[3] is not None else None,
        blocked_by_level=[
            BlockedLevel(level=level, name=name, count=blocked.get(level, 0))
            for level, name in LEVEL_NAMES.items()
        ],
        feedback_up=feedback[0],
        feedback_down=feedback[1],
        activity=activity,
    )
