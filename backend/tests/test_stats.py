from httpx import AsyncClient

from app.models import UserRole
from tests.conftest import auth_headers, create_user, parse_sse, requires_db
from tests.test_sessions import ask, make_datasource

pytestmark = requires_db


async def test_stats_counts_turns_queries_and_feedback(
    client: AsyncClient, analyst_headers: dict[str, str]
) -> None:
    r = await client.get("/api/stats", headers=analyst_headers)
    assert r.status_code == 200
    empty = r.json()
    assert empty["questions"] == 0 and empty["avg_duration_ms"] is None
    assert len(empty["activity"]) == 14

    datasource_id = await make_datasource()
    session = (
        await client.post(
            "/api/sessions", json={"datasource_id": datasource_id}, headers=analyst_headers
        )
    ).json()["id"]
    await ask(client, analyst_headers, session, "Топ регионов по выручке")
    await ask(client, analyst_headers, session, "Удали все заказы")
    await ask(client, analyst_headers, session, "Продажи за прошлый квартал")
    r = await client.post(
        f"/api/sessions/{session}/clarify",
        json={"answers": [{"ambiguity_id": "metric", "option_id": "revenue"}]},
        headers=analyst_headers,
    )
    parse_sse(r.text)
    messages = (
        await client.get(f"/api/sessions/{session}/messages", headers=analyst_headers)
    ).json()
    await client.post(
        f"/api/messages/{messages[1]['id']}/feedback", json={"score": 1}, headers=analyst_headers
    )

    stats = (
        await client.get(
            "/api/stats", params={"days": 3, "tz": "Asia/Almaty"}, headers=analyst_headers
        )
    ).json()
    # ответ на уточнение — продолжение вопроса, а не новый вопрос
    assert stats["questions"] == 3
    assert (stats["answered"], stats["clarifications"], stats["refused"]) == (2, 1, 1)
    assert stats["queries_ok"] == 2 and stats["avg_duration_ms"] is not None
    assert [b["name"] for b in stats["blocked_by_level"]][:2] == ["syntax", "readonly_policy"]
    assert (stats["feedback_up"], stats["feedback_down"]) == (1, 0)
    assert stats["sessions"] == 1 and stats["datasources_ready"] == 1
    today = stats["activity"][-1]
    assert len(stats["activity"]) == 3
    assert (today["questions"], today["answered"], today["refused"]) == (3, 2, 1)

    # чужие диалоги в сводку не попадают
    await create_user("other@test.kz", UserRole.ANALYST)
    other = await client.get("/api/stats", headers=await auth_headers(client, "other@test.kz"))
    assert other.json()["questions"] == 0


async def test_stats_rejects_unknown_timezone(
    client: AsyncClient, analyst_headers: dict[str, str]
) -> None:
    r = await client.get("/api/stats", params={"tz": "Mars/Olympus"}, headers=analyst_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
