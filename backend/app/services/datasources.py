"""Регистрация источников данных: проверка подключения и прав, интроспекция, индексация."""

import asyncio
import uuid
from datetime import UTC, datetime

import asyncpg
import structlog
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.security import decrypt, encrypt
from app.models import Datasource, DatasourceStatus
from app.schemas.schema_snapshot import SchemaSnapshot
from app.services import target_db
from app.services.indexer import get_indexer

log = structlog.get_logger()

_background: set[asyncio.Task[None]] = set()


async def verify_connection(url: str) -> None:
    """Проверяет, что БД доступна и роль не может ничего изменить."""
    if not target_db.is_postgres_url(url):
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_datasource",
            "Поддерживается только PostgreSQL: postgresql://user:password@host:port/dbname",
        )
    try:
        conn = await target_db.connect(url)
    except (OSError, TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError) as e:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "datasource_unreachable",
            f"Не удалось подключиться к БД: {type(e).__name__}: {e}",
        ) from e
    try:
        violations = await target_db.readonly_violations(conn)
    finally:
        await conn.close()
    if violations:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "datasource_not_readonly",
            "Роль подключения должна иметь права только на чтение. Нарушения: "
            + "; ".join(violations),
        )


async def create_datasource(
    db: AsyncSession, owner_id: uuid.UUID, name: str, url: str
) -> Datasource:
    await verify_connection(url)
    datasource = Datasource(
        owner_id=owner_id,
        name=name,
        dialect="postgres",
        connection_encrypted=encrypt(url),
        status=DatasourceStatus.INDEXING,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)
    return datasource


async def index_datasource(datasource_id: uuid.UUID) -> None:
    """Интроспекция схемы и индексация. Выполняется в фоне, статус пишется в БД."""
    async with get_sessionmaker()() as db:
        datasource = await db.get(Datasource, datasource_id)
        if datasource is None:
            return
        datasource.status, datasource.error = DatasourceStatus.INDEXING, None
        await db.commit()
        try:
            url = decrypt(datasource.connection_encrypted)
            pool = await target_db.target_pools.get(datasource_id, url)
            async with pool.acquire() as conn:
                snapshot = await target_db.introspect(conn, datasource_id)
            await get_indexer().index(snapshot)
        except Exception as e:
            log.warning("datasource_index_failed", datasource_id=str(datasource_id), error=str(e))
            datasource.status = DatasourceStatus.ERROR
            datasource.error = f"{type(e).__name__}: {e}"[:1000]
        else:
            datasource.schema_snapshot = snapshot.model_dump(mode="json")
            datasource.status = DatasourceStatus.READY
            datasource.indexed_at = datetime.now(UTC)
            log.info(
                "datasource_indexed",
                datasource_id=str(datasource_id),
                tables=len(snapshot.tables),
            )
        await db.commit()


def schedule_indexing(datasource_id: uuid.UUID) -> None:
    """Запускает индексацию, не блокируя запрос (ссылка на задачу хранится до завершения)."""
    task = asyncio.create_task(index_datasource(datasource_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def wait_background() -> None:
    """Для тестов и корректного завершения: дождаться фоновых индексаций."""
    if _background:
        await asyncio.gather(*_background, return_exceptions=True)


def tables_count(datasource: Datasource) -> int | None:
    if datasource.schema_snapshot is None:
        return None
    return len(SchemaSnapshot.model_validate(datasource.schema_snapshot).tables)
