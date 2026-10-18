"""Миграции применяются и откатываются, а модели не расходятся с миграциями.

Нужна отдельная БД (TEST_DATABASE_URL): тест откатывает схему до base.
Локально её создаёт `make test-backend`, в CI — сервис postgres.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import get_settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL не задан")


@pytest.fixture
def alembic_cfg(monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("APP_DATABASE_URL", TEST_DATABASE_URL)
    get_settings.cache_clear()
    yield Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    get_settings.cache_clear()


def test_upgrade_downgrade_cycle(alembic_cfg: Config) -> None:
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)  # падает, если модели изменены без новой миграции
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
