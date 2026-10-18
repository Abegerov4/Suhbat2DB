"""Действия при старте: первый администратор и демо-источник данных."""

import structlog
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.security import hash_password
from app.models import Datasource, User, UserRole
from app.services import datasources

log = structlog.get_logger()


async def ensure_admin(settings: Settings) -> User | None:
    if not settings.admin_email or settings.admin_password is None:
        return None
    email = settings.admin_email.lower()
    async with get_sessionmaker()() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(settings.admin_password.get_secret_value()),
                role=UserRole.ADMIN,
            )
            db.add(user)
            await db.commit()
            log.info("admin_created", email=email)
        return user


async def ensure_demo_datasource(settings: Settings, admin: User | None) -> None:
    """Регистрирует демо-БД, если её ещё нет. Ошибки не мешают запуску приложения."""
    if settings.demo_datasource_url is None or admin is None:
        return
    async with get_sessionmaker()() as db:
        exists = await db.scalar(
            select(Datasource.id).where(Datasource.name == settings.demo_datasource_name)
        )
        if exists is not None:
            return
        try:
            datasource = await datasources.create_datasource(
                db,
                admin.id,
                settings.demo_datasource_name,
                settings.demo_datasource_url.get_secret_value(),
            )
        except AppError as e:
            log.warning("demo_datasource_skipped", reason=e.message, hint="выполните make seed")
            return
    datasources.schedule_indexing(datasource.id)
    log.info("demo_datasource_registered", datasource_id=str(datasource.id))


async def bootstrap(settings: Settings) -> None:
    admin = await ensure_admin(settings)
    await ensure_demo_datasource(settings, admin)
