from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def async_url(url: str) -> str:
    """postgresql://… → postgresql+asyncpg://… (в .env хранится URL без драйвера)."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise ValueError("APP_DATABASE_URL должен быть URL вида postgresql://user:pass@host/db")
    return f"postgresql+asyncpg://{rest}" if scheme in {"postgres", "postgresql"} else url


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(async_url(get_settings().app_database_url), pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: одна сессия на запрос."""
    async with get_sessionmaker()() as session:
        yield session
