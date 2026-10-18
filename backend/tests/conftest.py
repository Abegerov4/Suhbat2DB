import asyncio
import json
import os
import secrets
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pytest
from cryptography.fernet import Fernet

# Минимальный набор обязательных переменных (до импорта приложения)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
os.environ.setdefault("APP_DATABASE_URL", TEST_DATABASE_URL or "postgresql://app:app@localhost/app")
if TEST_DATABASE_URL:
    os.environ["APP_DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
os.environ.setdefault("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
# тесты не ходят во внешние сервисы, даже если make подгрузил .env
for var in (
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "DEMO_DATASOURCE_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "PROMPTS_FROM_LANGFUSE",
    "AGENT_MODE",
):
    os.environ.pop(var, None)

import asyncpg
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.agent.fake import FakeAgentRunner
from app.api.deps import get_runner
from app.core import db as core_db
from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models import User, UserRole
from app.services import chat
from app.services.datasources import wait_background
from app.services.target_db import target_pools

requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL не задан")

TABLES = ("feedback", "query_log", "messages", "chat_sessions", "datasources", "users")
PASSWORD = "correct-horse-battery"


# --- БД приложения -------------------------------------------------------------------------


@pytest.fixture(scope="session")
def migrated() -> None:
    assert TEST_DATABASE_URL
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")


@pytest.fixture
async def clean_db(migrated: None) -> AsyncIterator[None]:
    """Свежий движок на event loop теста и пустые таблицы."""
    get_settings.cache_clear()
    core_db.get_engine.cache_clear()
    core_db.get_sessionmaker.cache_clear()
    async with core_db.get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    chat._active_sessions.clear()
    yield
    await wait_background()
    await target_pools.close_all()
    await core_db.get_engine().dispose()
    core_db.get_engine.cache_clear()
    core_db.get_sessionmaker.cache_clear()


@pytest.fixture
async def client(clean_db: None) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_runner] = lambda: FakeAgentRunner(delay=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def create_user(email: str, role: UserRole) -> User:
    async with core_db.get_sessionmaker()() as db:
        user = User(email=email, password_hash=hash_password(PASSWORD), role=role)
        db.add(user)
        await db.commit()
        return user


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    await create_user("admin@test.kz", UserRole.ADMIN)
    return await auth_headers(client, "admin@test.kz")


@pytest.fixture
async def analyst_headers(client: AsyncClient) -> dict[str, str]:
    await create_user("analyst@test.kz", UserRole.ANALYST)
    return await auth_headers(client, "analyst@test.kz")


# --- Целевая БД для проверки подключений ---------------------------------------------------

TARGET_DB = "s2d_target_test"
READER, WRITER, ROLE_PASSWORD = "s2d_test_reader", "s2d_test_writer", "test-role-password"

TARGET_SCHEMA = f"""
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
REVOKE ALL ON DATABASE {TARGET_DB} FROM PUBLIC;
GRANT CONNECT ON DATABASE {TARGET_DB} TO {READER}, {WRITER};
GRANT USAGE ON SCHEMA public TO {READER}, {WRITER};

CREATE TABLE regions (id int PRIMARY KEY, name text NOT NULL);
COMMENT ON TABLE regions IS 'Регионы';
COMMENT ON COLUMN regions.name IS 'Название региона';
CREATE TABLE orders (
    id int PRIMARY KEY,
    region_id int NOT NULL REFERENCES regions (id),
    status text NOT NULL,
    amount numeric(12, 2)
);
COMMENT ON TABLE orders IS 'Заказы';
INSERT INTO regions SELECT g, 'Регион ' || g FROM generate_series(1, 5) g;
INSERT INTO orders
SELECT g, 1 + g % 5, (ARRAY['new', 'paid', 'cancelled'])[1 + g % 3], g * 10
FROM generate_series(1, 1000) g;
CREATE TABLE events (
    id int PRIMARY KEY,
    region_id int NOT NULL REFERENCES regions (id),
    created_at timestamptz NOT NULL,
    payload text
);
INSERT INTO events
SELECT g, 1 + g % 5, '2026-01-01'::timestamptz + g * interval '1 minute', 'e' || g
FROM generate_series(1, 20000) g;
ANALYZE;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READER}, {WRITER};
GRANT INSERT ON orders TO {WRITER};
"""


def url_with(url: str, *, user: str | None = None, password: str | None = None,
             db: str | None = None) -> str:  # fmt: skip
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    netloc = f"{host}:{parts.port}" if parts.port else host
    if user:
        netloc = f"{user}:{password}@{netloc}"
    elif parts.username:
        netloc = f"{parts.username}:{parts.password}@{netloc}"
    return urlunsplit((parts.scheme, netloc, f"/{db}" if db else parts.path, "", ""))


async def _setup_target(admin_url: str) -> None:
    conn = await asyncpg.connect(admin_url)
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TARGET_DB):
            await conn.execute(f"CREATE DATABASE {TARGET_DB}")
        for role in (READER, WRITER):
            exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role)
            verb = "ALTER" if exists else "CREATE"
            await conn.execute(f"{verb} ROLE {role} LOGIN PASSWORD '{ROLE_PASSWORD}'")
    finally:
        await conn.close()
    conn = await asyncpg.connect(url_with(admin_url, db=TARGET_DB))
    try:
        await conn.execute(TARGET_SCHEMA)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def target_urls() -> Iterator[dict[str, str]]:
    assert TEST_DATABASE_URL
    asyncio.run(_setup_target(TEST_DATABASE_URL))
    yield {
        "reader": url_with(TEST_DATABASE_URL, user=READER, password=ROLE_PASSWORD, db=TARGET_DB),
        "writer": url_with(TEST_DATABASE_URL, user=WRITER, password=ROLE_PASSWORD, db=TARGET_DB),
        "superuser": url_with(TEST_DATABASE_URL, db=TARGET_DB),
    }


# --- SSE ------------------------------------------------------------------------------------


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields.get("data", "null"))))
    return events
