from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as core_db
from app.models import Datasource
from app.services.datasources import wait_background
from tests.conftest import requires_db

pytestmark = requires_db


async def create(client: AsyncClient, headers: dict[str, str], url: str) -> Any:
    return await client.post(
        "/api/datasources", json={"name": "Тестовая БД", "connection_url": url}, headers=headers
    )


async def test_readonly_datasource_is_indexed(
    client: AsyncClient, admin_headers: dict[str, str], target_urls: dict[str, str]
) -> None:
    r = await create(client, admin_headers, target_urls["reader"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "indexing"
    datasource_id = r.json()["id"]

    await wait_background()
    [listed] = (await client.get("/api/datasources", headers=admin_headers)).json()
    assert listed["status"] == "ready"
    assert listed["tables_count"] == 3
    assert listed["indexed_at"] is not None

    schema = (
        await client.get(f"/api/datasources/{datasource_id}/schema", headers=admin_headers)
    ).json()
    assert schema["timezone"]
    tables = {t["name"]: t for t in schema["tables"]}
    assert set(tables) == {"events", "orders", "regions"}
    assert tables["regions"]["comment"] == "Регионы"
    assert tables["orders"]["row_estimate"] == 1000

    orders = {c["name"]: c for c in tables["orders"]["columns"]}
    assert orders["id"]["is_pk"] is True
    assert orders["region_id"]["fk"] == "public.regions.id"
    assert orders["status"]["sample_values"] == ["cancelled", "new", "paid"]
    assert orders["amount"]["sample_values"] is None  # не текстовый столбец
    assert orders["amount"]["data_type"] == "numeric(12,2)"
    regions = {c["name"]: c for c in tables["regions"]["columns"]}
    assert regions["name"]["comment"] == "Название региона"
    # уникальные значения маленького справочника тоже нужны агенту (value linking)
    assert regions["name"]["sample_values"] == [f"Регион {i}" for i in range(1, 6)]


async def test_connection_string_is_stored_encrypted(
    client: AsyncClient, admin_headers: dict[str, str], target_urls: dict[str, str]
) -> None:
    await create(client, admin_headers, target_urls["reader"])
    async with core_db.get_sessionmaker()() as db:
        stored = await db.scalar(select(Datasource.connection_encrypted))
    assert stored is not None
    assert b"test-role-password" not in stored


@pytest.mark.parametrize(
    ("role", "expected_fragment"),
    [
        ("writer", "public.orders"),
        ("superuser", "суперпользователем"),
    ],
)
async def test_writable_role_is_rejected(
    client: AsyncClient,
    admin_headers: dict[str, str],
    target_urls: dict[str, str],
    role: str,
    expected_fragment: str,
) -> None:
    r = await create(client, admin_headers, target_urls[role])
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "datasource_not_readonly"
    assert expected_fragment in error["message"]
    assert (await client.get("/api/datasources", headers=admin_headers)).json() == []


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("postgresql://u:p@127.0.0.1:1/db", "datasource_unreachable"),
        ("mysql://u:p@localhost/db", "unsupported_datasource"),
    ],
)
async def test_bad_connection_is_rejected(
    client: AsyncClient, admin_headers: dict[str, str], url: str, code: str
) -> None:
    r = await create(client, admin_headers, url)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code


async def test_schema_not_ready_reindex_delete(
    client: AsyncClient, admin_headers: dict[str, str], target_urls: dict[str, str]
) -> None:
    datasource_id = (await create(client, admin_headers, target_urls["reader"])).json()["id"]
    r = await client.get(f"/api/datasources/{datasource_id}/schema", headers=admin_headers)
    assert r.status_code == 409  # индексация ещё не завершилась
    assert r.json()["error"]["code"] == "schema_not_ready"
    await wait_background()

    r = await client.post(f"/api/datasources/{datasource_id}/reindex", headers=admin_headers)
    assert r.status_code == 202
    await wait_background()

    r = await client.delete(f"/api/datasources/{datasource_id}", headers=admin_headers)
    assert r.status_code == 204
    r = await client.get(f"/api/datasources/{datasource_id}/schema", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "datasource_not_found"
