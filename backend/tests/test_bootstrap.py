import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.bootstrap import bootstrap
from app.core import db as core_db
from app.core.config import get_settings
from app.models import Datasource, DatasourceStatus, User, UserRole
from app.services.datasources import wait_background
from tests.conftest import requires_db

pytestmark = requires_db


async def counts() -> tuple[int, int]:
    async with core_db.get_sessionmaker()() as db:
        admins = await db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
        )
        sources = await db.scalar(select(func.count()).select_from(Datasource))
    return admins or 0, sources or 0


async def test_bootstrap_is_idempotent(clean_db: None, target_urls: dict[str, str]) -> None:
    settings = get_settings().model_copy(
        update={
            "admin_email": "Root@Test.kz",
            "admin_password": SecretStr("root-password"),
            "demo_datasource_url": SecretStr(target_urls["reader"]),
        }
    )
    await bootstrap(settings)
    await bootstrap(settings)
    await wait_background()
    assert await counts() == (1, 1)

    async with core_db.get_sessionmaker()() as db:
        datasource = await db.scalar(select(Datasource))
    assert datasource is not None
    assert datasource.status == DatasourceStatus.READY


@pytest.mark.parametrize("url", ["postgresql://u:p@127.0.0.1:1/db"])
async def test_unreachable_demo_does_not_break_startup(
    clean_db: None, target_urls: dict[str, str], url: str
) -> None:
    settings = get_settings().model_copy(
        update={
            "admin_email": "root@test.kz",
            "admin_password": SecretStr("root-password"),
            "demo_datasource_url": SecretStr(url),
        }
    )
    await bootstrap(settings)
    assert await counts() == (1, 0)
