"""LangGraphAgentRunner: поток графа → события SSE (CONTRACTS §2) + трассировка Langfuse."""

from collections.abc import AsyncIterator
from typing import Any, cast

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.agent.runner import RunContext
from app.agent.state import AgentContext, AgentState, new_turn
from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.core.security import decrypt
from app.models import Datasource
from app.schemas.agent import (
    EVENT_PAYLOADS,
    AgentEvent,
    ClarificationAnswer,
    ClarificationRequest,
    DoneEvent,
    EventType,
)
from app.schemas.schema_snapshot import SchemaSnapshot
from app.services.target_db import target_pools
from app.validator import Limits

log = structlog.get_logger()


class LangGraphAgentRunner:
    def __init__(
        self, graph: CompiledStateGraph[AgentState, AgentContext], settings: Settings
    ) -> None:
        self.graph = graph
        self.settings = settings

    async def _context(self, ctx: RunContext) -> AgentContext:
        async with get_sessionmaker()() as db:
            datasource = await db.get(Datasource, ctx.datasource_id)
        if datasource is None or datasource.schema_snapshot is None:
            raise RuntimeError("Источник данных не найден или не проиндексирован")
        pool = await target_pools.get(datasource.id, decrypt(datasource.connection_encrypted))
        return AgentContext(
            snapshot=SchemaSnapshot.model_validate(datasource.schema_snapshot),
            pool=pool,
            limits=Limits.from_settings(),
        )

    def _config(self, ctx: RunContext, trace_id: str | None) -> RunnableConfig:
        callbacks: list[Any] = []
        if trace_id is not None:
            from langfuse.langchain import CallbackHandler

            callbacks.append(CallbackHandler(trace_context={"trace_id": trace_id}))
        return {
            "configurable": {"thread_id": str(ctx.session_id)},
            "callbacks": callbacks,
            "run_name": "suhbat2db-turn",
            "metadata": {
                "langfuse_session_id": str(ctx.session_id),
                "langfuse_user_id": str(ctx.user_id),
                "langfuse_tags": ["agent"],
                "datasource_id": str(ctx.datasource_id),
            },
        }

    def run(self, ctx: RunContext, question: str) -> AsyncIterator[AgentEvent]:
        return self._stream(new_turn(question), ctx)

    def resume(
        self,
        ctx: RunContext,
        clarification: ClarificationRequest,
        answers: list[ClarificationAnswer],
    ) -> AsyncIterator[AgentEvent]:
        payload = [a.model_dump() for a in answers]
        return self._stream(Command(resume=payload), ctx)

    async def _stream(self, graph_input: Any, ctx: RunContext) -> AsyncIterator[AgentEvent]:
        trace_id = None
        if self.settings.langfuse_enabled:
            from langfuse import Langfuse

            trace_id = Langfuse.create_trace_id()
        context = await self._context(ctx)
        awaiting = False
        async for part in self.graph.astream(
            graph_input,
            self._config(ctx, trace_id),
            context=context,
            stream_mode=["custom", "updates"],
        ):
            mode, chunk = cast(tuple[str, Any], part)
            if mode == "custom":
                event_type: EventType = chunk["type"]
                yield AgentEvent(
                    type=event_type, data=EVENT_PAYLOADS[event_type].model_validate(chunk["data"])
                )
            elif isinstance(chunk, dict) and "__interrupt__" in chunk:
                awaiting = True
                request = ClarificationRequest.model_validate(chunk["__interrupt__"][0].value)
                yield AgentEvent(type="clarification", data=request)
        yield AgentEvent(
            type="done", data=DoneEvent(trace_id=trace_id, awaiting_clarification=awaiting)
        )
