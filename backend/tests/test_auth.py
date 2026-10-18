from httpx import AsyncClient

from tests.conftest import requires_db

pytestmark = requires_db


async def test_register_login_me(client: AsyncClient) -> None:
    creds = {"email": "User@Example.kz", "password": "long-enough-password"}
    r = await client.post("/api/auth/register", json=creds)
    assert r.status_code == 201
    assert r.json()["email"] == "user@example.kz"
    assert r.json()["role"] == "analyst"

    r = await client.post(
        "/api/auth/login", json={**creds, "email": "user@example.kz"}
    )  # email без учёта регистра
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "user@example.kz"


async def test_register_duplicate_email(client: AsyncClient) -> None:
    creds = {"email": "dup@example.kz", "password": "long-enough-password"}
    assert (await client.post("/api/auth/register", json=creds)).status_code == 201
    r = await client.post("/api/auth/register", json={**creds, "email": "DUP@example.kz"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


async def test_login_wrong_password_and_unknown_email(client: AsyncClient) -> None:
    creds = {"email": "a@example.kz", "password": "long-enough-password"}
    await client.post("/api/auth/register", json=creds)
    for body in ({**creds, "password": "wrong-password"}, {**creds, "email": "no@example.kz"}):
        r = await client.post("/api/auth/login", json=body)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    r = await client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_validation_error_format(client: AsyncClient) -> None:
    r = await client.post("/api/auth/register", json={"email": "bad", "password": "short"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error"
    assert {tuple(d["loc"]) for d in body["details"]} == {("body", "email"), ("body", "password")}


async def test_analyst_cannot_manage_datasources(
    client: AsyncClient, analyst_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/datasources",
        json={"name": "x", "connection_url": "postgresql://a:b@c/d"},
        headers=analyst_headers,
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_unknown_route_uses_error_format(client: AsyncClient) -> None:
    r = await client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
