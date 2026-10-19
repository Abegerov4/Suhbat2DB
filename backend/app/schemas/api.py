"""Модели запросов и ответов REST API (CONTRACTS §1)."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DatasourceStatus, MessageRole, UserRole
from app.schemas.agent import (
    ChartSpec,
    ClarificationAnswer,
    ClarificationRequest,
    ErrorEvent,
    QueryResult,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ----------------------------------------------------------------------------------


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


# --- Datasources ---------------------------------------------------------------------------


class DatasourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    connection_url: str = Field(
        min_length=1,
        max_length=2000,
        description="postgresql://user:password@host:port/dbname (роль только для чтения)",
    )


class DatasourceOut(ORMModel):
    id: uuid.UUID
    name: str
    dialect: Literal["postgres"]
    status: DatasourceStatus
    error: str | None
    indexed_at: datetime | None
    tables_count: int | None = None


# --- Sessions & messages -------------------------------------------------------------------


class SessionCreate(BaseModel):
    datasource_id: uuid.UUID
    title: str | None = Field(default=None, max_length=200)


class SessionOut(ORMModel):
    id: uuid.UUID
    datasource_id: uuid.UUID
    title: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ClarifyRequest(BaseModel):
    answers: list[ClarificationAnswer] = Field(min_length=1)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
    sql: str | None = None
    validation_report: dict[str, Any] | None = None
    result: QueryResult | None = None
    chart_spec: ChartSpec | None = None
    clarification: ClarificationRequest | None = None
    error: ErrorEvent | None = None
    trace_id: str | None = None


class FeedbackCreate(BaseModel):
    score: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=2000)


# --- Stats ---------------------------------------------------------------------------------


class DailyActivity(BaseModel):
    date: date
    questions: int = 0
    answered: int = 0
    clarifications: int = 0
    refused: int = 0


class BlockedLevel(BaseModel):
    level: int
    name: str
    count: int


class StatsOut(BaseModel):
    """Ход диалога завершается ответом (answered), уточнением или отказом (refused)."""

    questions: int
    answered: int
    clarifications: int
    refused: int
    sessions: int
    datasources: int
    datasources_ready: int
    queries_ok: int
    queries_blocked: int
    queries_failed: int
    avg_duration_ms: int | None
    blocked_by_level: list[BlockedLevel]
    feedback_up: int
    feedback_down: int
    activity: list[DailyActivity]
