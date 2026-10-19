"""Ход агента не зависит от соединения: обрыв не теряет ответ, /stop сохраняет остановку."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

from httpx import AsyncClient

from app.models import UserRole
from app.schemas.agent import AgentEvent, AnswerEvent, DoneEvent, StepEvent
from app.services import chat
from tests.conftest import auth_headers, create_user, parse_sse, requires_db
from tests.test_sessions import session_id  # noqa: F401 — фикстура

pytestmark = requires_db


class SlowRunner:
    """Первый шаг сразу, ответ — только после release (имитация долгого LLM)."""

    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def run(self) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(type="step", data=StepEvent(node="generate_sql", status="started"))
        await self.release.wait()
        yield AgentEvent(type="answer", data=AnswerEvent(text="готово"))
        yield AgentEvent(type="done", data=DoneEvent())


async def history(client: AsyncClient, headers: dict[str, str], sid: str) -> list[Any]:
    r = await client.get(f"/api/sessions/{sid}/messages", headers=headers)
    messages: list[Any] = r.json()
    return messages


async def test_turn_is_saved_after_client_disconnect(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    session_id: str,  # noqa: F811
) -> None:
    sid = uuid.UUID(session_id)
    runner = SlowRunner()
    chat.acquire_session(sid)
    stream = chat.stream_turn(sid, runner.run())
    assert b"event: step" in await anext(stream)
    await stream.aclose()  # браузер закрыл вкладку посреди ответа

    runner.release.set()
    await chat.wait_turns()
    messages = await history(client, analyst_headers, session_id)
    assert messages[-1]["content"] == "готово"
    assert sid not in chat._active_sessions


async def test_stop_cancels_and_saves_the_turn(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    session_id: str,  # noqa: F811
) -> None:
    sid = uuid.UUID(session_id)
    chat.acquire_session(sid)
    stream = chat.stream_turn(sid, SlowRunner().run())
    await anext(stream)

    r = await client.post(f"/api/sessions/{session_id}/stop", headers=analyst_headers)
    assert r.status_code == 204
    events = parse_sse(b"".join([chunk async for chunk in stream]).decode())
    assert [t for t, _ in events] == ["error", "done"]
    assert events[0][1]["code"] == "cancelled"

    messages = await history(client, analyst_headers, session_id)
    assert messages[-1]["error"]["code"] == "cancelled"
    assert sid not in chat._active_sessions

    # без активного хода — не ошибка; чужая сессия — 404
    r = await client.post(f"/api/sessions/{session_id}/stop", headers=analyst_headers)
    assert r.status_code == 204
    await create_user("other@test.kz", UserRole.ANALYST)
    other = await auth_headers(client, "other@test.kz")
    r = await client.post(f"/api/sessions/{session_id}/stop", headers=other)
    assert r.status_code == 404
