"""Интерфейс агента. Заглушка (FakeAgentRunner) заменяется на LangGraph-агента в роли 5."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from app.schemas.agent import AgentEvent, ClarificationAnswer, ClarificationRequest


@dataclass(frozen=True)
class RunContext:
    session_id: uuid.UUID  # = thread_id графа LangGraph
    datasource_id: uuid.UUID
    user_id: uuid.UUID


class AgentRunner(Protocol):
    """Поток событий заканчивается событием `done` (или `error`, затем `done`).

    Сохранением сообщений занимается API-слой: он подставляет message_id в `done`.
    """

    def run(self, ctx: RunContext, question: str) -> AsyncIterator[AgentEvent]: ...

    def resume(
        self,
        ctx: RunContext,
        clarification: ClarificationRequest,
        answers: list[ClarificationAnswer],
    ) -> AsyncIterator[AgentEvent]: ...
