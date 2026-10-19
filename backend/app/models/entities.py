"""Таблицы БД приложения (docs/roles/02_database.md, раздел 2.3).

Анализируемые данные пользователей здесь не хранятся: только метаданные
подключений, история диалогов и журнал выполненных запросов.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAt, UUIDPk


def str_enum(enum: type[StrEnum]) -> Enum:
    # VARCHAR + CHECK вместо нативного ENUM: новые значения добавляются без ALTER TYPE.
    # CHECK задаётся явно через enum_check(), иначе autogenerate дублирует ограничение.
    return Enum(
        enum,
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


def enum_check(column: str, enum: type[StrEnum]) -> CheckConstraint:
    values = ", ".join(f"'{m.value}'" for m in enum)
    return CheckConstraint(f"{column} IN ({values})", name=column)


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"


class DatasourceStatus(StrEnum):
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class QueryStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"
    ERROR = "error"


class User(UUIDPk, CreatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)  # хранится в нижнем регистре
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole), default=UserRole.ANALYST)

    __table_args__ = (enum_check("role", UserRole),)


class Datasource(UUIDPk, CreatedAt, Base):
    __tablename__ = "datasources"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    dialect: Mapped[str] = mapped_column(String(32), default="postgres")
    # строка подключения, зашифрованная Fernet (ключ ENCRYPTION_KEY в env)
    connection_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[DatasourceStatus] = mapped_column(
        str_enum(DatasourceStatus), default=DatasourceStatus.INDEXING
    )
    error: Mapped[str | None] = mapped_column(Text)
    schema_snapshot: Mapped[dict[str, Any] | None]
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (enum_check("status", DatasourceStatus),)


class ChatSession(UUIDPk, CreatedAt, Base):
    """Диалог пользователя. id совпадает с thread_id графа LangGraph."""

    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    datasource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasources.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_chat_sessions_user_id_updated_at", "user_id", "updated_at"),)


class Message(UUIDPk, CreatedAt, Base):
    __tablename__ = "messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    sql: Mapped[str | None] = mapped_column(Text)
    validation_report: Mapped[dict[str, Any] | None]
    result_meta: Mapped[dict[str, Any] | None]  # columns, row_count, truncated, первые строки
    chart_spec: Mapped[dict[str, Any] | None]
    clarification: Mapped[dict[str, Any] | None]
    error: Mapped[dict[str, Any] | None]  # {code, message} отказа или ошибки агента
    trace_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_messages_session_id_created_at", "session_id", "created_at"),
        enum_check("role", MessageRole),
    )


class Feedback(UUIDPk, CreatedAt, Base):
    __tablename__ = "feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("score IN (-1, 1)", name="score"),
        UniqueConstraint("message_id", "user_id"),
    )


class QueryLog(UUIDPk, CreatedAt, Base):
    """Журнал всех SQL, которые агент пытался выполнить, включая заблокированные."""

    __tablename__ = "query_log"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )
    sql: Mapped[str] = mapped_column(Text)
    status: Mapped[QueryStatus] = mapped_column(str_enum(QueryStatus))
    blocked_level: Mapped[int | None] = mapped_column(SmallInteger)
    duration_ms: Mapped[int | None]
    row_count: Mapped[int | None]

    __table_args__ = (
        CheckConstraint("blocked_level BETWEEN 1 AND 5", name="blocked_level"),
        enum_check("status", QueryStatus),
        Index(None, "created_at"),
    )
