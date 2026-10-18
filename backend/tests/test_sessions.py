from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.agent.runner import RunContext
from app.api.deps import get_runner
from app.core import db as core_db
from app.core.security import encrypt
from app.main import app
from app.models import Datasource, DatasourceStatus, QueryLog, QueryStatus, User, UserRole
from app.schemas.agent import AgentEvent, ClarificationAnswer, ClarificationRequest
from app.services import chat
from tests.conftest import auth_headers, create_user, parse_sse, requires_db

pytestmark = requires_db


async def make_datasource(status: DatasourceStatus = DatasourceStatus.READY) -> str:
    async with core_db.get_sessionmaker()() as db:
        owner = await db.scalar(select(User).where(User.role == UserRole.ADMIN))
        if owner is None:
            owner = User(email="owner@test.kz", password_hash="x", role=UserRole.ADMIN)
            db.add(owner)
            await db.flush()
        datasource = Datasource(
            owner_id=owner.id,
            name="Демо",
            dialect="postgres",
            connection_encrypted=encrypt("postgresql://r:p@h/d"),
            status=status,
        )
        db.add(datasource)
        await db.commit()
        return str(datasource.id)


@pytest.fixture
async def session_id(client: AsyncClient, analyst_headers: dict[str, str]) -> str:
    datasource_id = await make_datasource()
    r = await client.post(
        "/api/sessions", json={"datasource_id": datasource_id}, headers=analyst_headers
    )
    assert r.status_code == 201
    assert r.json()["title"] == "Новый диалог"
    return str(r.json()["id"])


async def ask(
    client: AsyncClient, headers: dict[str, str], session_id: str, content: str
) -> list[tuple[str, Any]]:
    r = await client.post(
        f"/api/sessions/{session_id}/messages", json={"content": content}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)


async def test_answer_stream_and_history(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    events = await ask(client, analyst_headers, session_id, "Топ регионов по выручке")
    types = [t for t, _ in events]
    assert types[-1] == "done"
    assert types.count("validation") == 5
    assert {"step", "sql", "result", "answer", "chart"} <= set(types)
    done = events[-1][1]
    assert done["awaiting_clarification"] is False
    assert done["message_id"]

    messages = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=analyst_headers)
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    answer = messages[1]
    assert answer["id"] == done["message_id"]
    assert answer["sql"].startswith("SELECT")
    assert answer["validation_report"]["passed"] is True
    assert answer["result"]["row_count"] == 5
    assert answer["chart_spec"]["type"] == "bar"
    assert "Алматы" in answer["content"]

    [session] = (await client.get("/api/sessions", headers=analyst_headers)).json()
    assert session["title"] == "Топ регионов по выручке"

    async with core_db.get_sessionmaker()() as db:
        log = await db.scalar(select(QueryLog))
    assert log is not None and log.status == QueryStatus.OK and log.row_count == 5


async def test_clarification_flow(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    events = await ask(client, analyst_headers, session_id, "Продажи за прошлый квартал")
    assert [t for t, _ in events][-2:] == ["clarification", "done"]
    assert events[-1][1]["awaiting_clarification"] is True
    clarification = events[-2][1]
    assert [a["id"] for a in clarification["ambiguities"]] == ["metric", "quarter"]

    # пока уточнение не получено, новый вопрос не принимается
    r = await client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "ещё"}, headers=analyst_headers
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "clarification_pending"

    url = f"/api/sessions/{session_id}/clarify"
    bad = {"answers": [{"ambiguity_id": "metric", "option_id": "nope"}]}
    r = await client.post(url, json=bad, headers=analyst_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_clarification"

    good = {
        "answers": [
            {"ambiguity_id": "metric", "option_id": "revenue"},
            {"ambiguity_id": "quarter", "free_text": "как в отчёте для совета директоров"},
        ]
    }
    r = await client.post(url, json=good, headers=analyst_headers)
    assert r.status_code == 200
    events = parse_sse(r.text)
    answer = "".join(d["text"] for t, d in events if t == "answer")
    assert "Учтено уточнение: Выручка, как в отчёте для совета директоров" in answer

    messages = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=analyst_headers)
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["clarification"]["ambiguities"][0]["id"] == "metric"
    assert messages[2]["content"] == (
        "Уточнение: продажи → Выручка; квартал → как в отчёте для совета директоров"
    )

    r = await client.post(url, json=good, headers=analyst_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_pending_clarification"


async def test_refusal(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    events = await ask(client, analyst_headers, session_id, "Удали все заказы")
    assert [t for t, _ in events][-2:] == ["error", "done"]
    assert events[-2][1]["code"] == "refused"
    messages = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=analyst_headers)
    ).json()
    assert "только читать" in messages[1]["content"]


class FailingRunner:
    async def run(self, ctx: RunContext, question: str) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("boom")
        yield  # pragma: no cover

    async def resume(
        self,
        ctx: RunContext,
        clarification: ClarificationRequest,
        answers: list[ClarificationAnswer],
    ) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("boom")
        yield  # pragma: no cover


async def test_agent_failure_becomes_error_event(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    app.dependency_overrides[get_runner] = FailingRunner
    events = await ask(client, analyst_headers, session_id, "вопрос")
    assert [t for t, _ in events] == ["error", "done"]
    assert events[0][1]["code"] == "internal_error"
    assert not chat._active_sessions  # сессия освобождена


async def test_busy_session_and_not_ready_datasource(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    import uuid

    chat.acquire_session(uuid.UUID(session_id))
    r = await client.post(
        f"/api/sessions/{session_id}/messages", json={"content": "x"}, headers=analyst_headers
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "session_busy"
    chat.release_session(uuid.UUID(session_id))

    datasource_id = await make_datasource(DatasourceStatus.INDEXING)
    other = (
        await client.post(
            "/api/sessions", json={"datasource_id": datasource_id}, headers=analyst_headers
        )
    ).json()["id"]
    r = await client.post(
        f"/api/sessions/{other}/messages", json={"content": "x"}, headers=analyst_headers
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "datasource_not_ready"


async def test_sessions_are_private(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    await create_user("other@test.kz", UserRole.ANALYST)
    other = await auth_headers(client, "other@test.kz")
    assert (await client.get("/api/sessions", headers=other)).json() == []
    r = await client.get(f"/api/sessions/{session_id}/messages", headers=other)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "session_not_found"


async def test_feedback(
    client: AsyncClient, analyst_headers: dict[str, str], session_id: str
) -> None:
    await ask(client, analyst_headers, session_id, "Топ регионов")
    user_msg, answer = (
        await client.get(f"/api/sessions/{session_id}/messages", headers=analyst_headers)
    ).json()

    url = f"/api/messages/{answer['id']}/feedback"
    assert (await client.post(url, json={"score": 1}, headers=analyst_headers)).status_code == 204
    r = await client.post(url, json={"score": -1, "comment": "не то"}, headers=analyst_headers)
    assert r.status_code == 204  # повторная оценка заменяет первую

    r = await client.post(url, json={"score": 5}, headers=analyst_headers)
    assert r.status_code == 422
    r = await client.post(
        f"/api/messages/{user_msg['id']}/feedback", json={"score": 1}, headers=analyst_headers
    )
    assert r.status_code == 404  # оценивать можно только ответы ассистента

    await create_user("other@test.kz", UserRole.ANALYST)
    other = await auth_headers(client, "other@test.kz")
    assert (await client.post(url, json={"score": 1}, headers=other)).status_code == 404
