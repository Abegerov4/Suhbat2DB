"""Узлы LangGraph-агента (граф — README §5, контракт событий — CONTRACTS §2).

Узел читает состояние, отправляет события в поток (get_stream_writer) и возвращает
только изменения состояния. Маршрут выбирают route-функции в graph.py по полю route,
а не LLM.
"""

import functools
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import BaseModel

from app.agent.charts import choose_chart
from app.agent.llm import LLM, NodeKey
from app.agent.prompts import PromptName, PromptRegistry
from app.agent.retrieval.linker import SchemaLinker, full_schema
from app.agent.retrieval.store import SchemaStore
from app.agent.state import AgentContext, AgentState, Clarification, Feedback, Turn
from app.schemas.agent import (
    Ambiguity,
    AmbiguityType,
    AnswerEvent,
    ClarificationOption,
    ClarificationRequest,
    ErrorEvent,
    EventType,
    NodeName,
    QueryResult,
    SqlEvent,
    StepEvent,
    ValidationLevelResult,
)
from app.validator import ExecutionError, execute_readonly, explain, validate

log = structlog.get_logger()

Update = dict[str, Any]
Node = Callable[
    ["AgentNodes", AgentState, Runtime[AgentContext], RunnableConfig], Awaitable[Update]
]

REFUSALS: dict[str, str] = {
    "refused": "Я могу только читать данные: изменение, удаление и создание недоступны.",
    "unsafe_input": "Не могу выполнить эту просьбу: я отвечаю только на вопросы о данных.",
    "out_of_scope": "Я отвечаю только на вопросы о данных подключённой базы.",
    "unsafe_sql": "Сгенерированный запрос нарушает политику «только чтение» и не будет выполнен.",
    "max_attempts": "Не удалось построить корректный запрос за несколько попыток. "
    "Попробуйте переформулировать вопрос.",
    "no_connection": "Нет подключения к базе данных.",
}


# --- Структурированные ответы LLM ------------------------------------------------------------


class GuardVerdict(BaseModel):
    decision: Literal["allow", "modify", "injection", "off_topic"]
    reason: str


class OptionDraft(BaseModel):
    label: str
    description: str
    interpretation: str


class AmbiguityDraft(BaseModel):
    type: AmbiguityType
    span: str
    options: list[OptionDraft]


class AmbiguityVerdict(BaseModel):
    status: Literal["clear", "ambiguous", "out_of_scope"]
    ambiguities: list[AmbiguityDraft]
    reason: str


class GeneratedSQL(BaseModel):
    sql: str
    explanation: str


# --- Служебное ---------------------------------------------------------------------------


def emit(event: EventType, payload: BaseModel) -> None:
    get_stream_writer()({"type": event, "data": payload.model_dump(mode="json")})


def step(name: NodeName) -> Callable[[Node], Node]:
    """События step started/finished вокруг узла; detail — из ключа «_detail» обновления."""

    def decorator(fn: Node) -> Node:
        @functools.wraps(fn)
        async def wrapper(
            self: "AgentNodes",
            state: AgentState,
            runtime: Runtime[AgentContext],
            config: RunnableConfig,
        ) -> Update:
            emit("step", StepEvent(node=name, status="started"))
            update = await fn(self, state, runtime, config)
            detail = update.pop("_detail", None)
            emit("step", StepEvent(node=name, status="finished", detail=detail))
            return update

        return wrapper

    return decorator


def refusal(code: str, message: str | None = None) -> Update:
    return {"route": "refuse", "error": {"code": code, "message": message or REFUSALS[code]}}


def dialog_context(state: AgentState, turns: int = 2) -> str:
    history = state.get("history", [])[-turns:]
    if not history:
        return ""
    parts = [f"Вопрос: {t['question']}\nSQL: {t['sql'] or '—'}" for t in history]
    return "<dialog>\nПредыдущие вопросы в этом диалоге:\n" + "\n\n".join(parts) + "\n</dialog>"


def clarifications_text(items: list[Clarification], title: str) -> str:
    if not items:
        return ""
    lines = [f"- {c['span']}: {c['choice']} → {c['interpretation']}" for c in items]
    return f"{title}:\n" + "\n".join(lines)


def schema_summary(context: AgentContext) -> str:
    return "\n".join(f"- {t.name}: {t.comment or ''}" for t in context.snapshot.tables)


NUMBER_RE = re.compile(r"\d[\d\s]{3,}\d")


def ungrounded_numbers(answer: str, result: QueryResult) -> list[str]:
    """Длинные числа из пояснения, которых нет в результате (контроль галлюцинаций)."""
    values = {str(v) for row in result.rows for v in row if isinstance(v, int | float)}
    values |= {str(int(v)) for row in result.rows for v in row if isinstance(v, float)}
    found = [n.replace(" ", "").replace(" ", "") for n in NUMBER_RE.findall(answer)]
    return [n for n in found if n not in values]


# --- Узлы --------------------------------------------------------------------------------


@dataclass
class AgentNodes:
    llm: LLM
    prompts: PromptRegistry
    linker: SchemaLinker
    store: SchemaStore
    few_shot: int = 3
    max_attempts: int = 3
    max_clarification_rounds: int = 2
    # Переключатели экспериментов (evals, docs/roles/07_evals.md); в работе всё включено
    clarify_enabled: bool = True  # эксперимент 2: агент без уточнения
    schema_linking_enabled: bool = True  # эксперимент 3: полная схема вместо отбора
    semantic_checks: bool = True  # эксперимент 4: без уровней 3 (схема) и 4 (EXPLAIN)
    explain_enabled: bool = True  # пояснение не влияет на метрики evals и не оплачивается

    def _messages(
        self, name: PromptName, user: str, **variables: str
    ) -> tuple[list[BaseMessage], RunnableConfig]:
        prompt = self.prompts.get(name)
        messages = [SystemMessage(prompt.compile(**variables)), HumanMessage(user)]
        return messages, {"metadata": prompt.metadata()}

    def _config(self, base: RunnableConfig, extra: RunnableConfig) -> RunnableConfig:
        merged: RunnableConfig = dict(base)  # type: ignore[assignment]
        merged["metadata"] = {**base.get("metadata", {}), **extra.get("metadata", {})}
        return merged

    async def _structured[T: BaseModel](
        self,
        node: NodeKey,
        prompt: PromptName,
        user: str,
        schema: type[T],
        config: RunnableConfig,
        **variables: str,
    ) -> T:
        messages, extra = self._messages(prompt, user, **variables)
        return await self.llm.structured(node, messages, schema, self._config(config, extra))

    @step("guard_input")
    async def guard_input(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        user = f"{dialog_context(state)}\n\n<user_message>\n{state['question']}\n</user_message>"
        verdict = await self._structured(
            "guard", "guard", user, GuardVerdict, config,
            schema_summary=schema_summary(runtime.context),
        )  # fmt: skip
        if verdict.decision == "allow":
            return {"route": "ok"}
        code = {"modify": "refused", "injection": "unsafe_input", "off_topic": "out_of_scope"}
        return {**refusal(code[verdict.decision]), "_detail": verdict.reason}

    @step("schema_linking")
    async def schema_linking(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        history = state.get("history", [])
        query = state["resolved_question"]
        if history and len(state["question"]) < 60:  # короткий follow-up: «а по месяцам?»
            query = f"{history[-1]['question']}\n{query}"
        snapshot = runtime.context.snapshot
        linked = (
            await self.linker.link(query, snapshot)
            if self.schema_linking_enabled
            else full_schema(snapshot)
        )
        examples = await self.store.search_examples(
            snapshot.datasource_id, state["resolved_question"], self.few_shot
        )
        return {
            "linked_schema": linked.render(),
            "linked_tables": linked.table_names,
            "examples": [{"question": e.question, "sql": e.sql} for e in examples],
            "_detail": "Таблицы: " + ", ".join(linked.table_names),
        }

    @step("detect_ambiguity")
    async def detect_ambiguity(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        if not self.clarify_enabled:
            return {"route": "generate", "_detail": "Уточнение отключено"}
        if state.get("clarification_rounds", 0) >= self.max_clarification_rounds:
            return {"route": "generate", "_detail": "Лимит уточнений исчерпан"}
        user = "\n\n".join(
            part
            for part in (
                f"<schema>\n{state['linked_schema']}\n</schema>",
                dialog_context(state),
                clarifications_text(state.get("clarifications", []), "Прошлые уточнения"),
                f"Вопрос: {state['resolved_question']}",
            )
            if part
        )
        verdict = await self._structured(
            "ambiguity", "ambiguity", user, AmbiguityVerdict, config,
            today=runtime.context.today.isoformat(),
        )  # fmt: skip
        if verdict.status == "out_of_scope":
            return refusal("out_of_scope")
        ambiguities = [a for a in verdict.ambiguities if len(a.options) >= 2][:2]
        if verdict.status == "clear" or not ambiguities:
            return {"route": "generate", "_detail": verdict.reason}

        request_items, interpretations, spans = [], {}, {}
        for i, draft in enumerate(ambiguities, 1):
            aid = f"a{i}"
            spans[aid] = draft.span
            options = []
            for j, option in enumerate(draft.options[:4], 1):
                oid = f"{aid}o{j}"
                interpretations[oid] = option.interpretation
                options.append(
                    ClarificationOption(
                        id=oid, label=option.label, description=option.description or None
                    )
                )
            request_items.append(
                Ambiguity(id=aid, type=draft.type, span=draft.span, options=options)
            )
        request = ClarificationRequest(
            question="Уточните, пожалуйста, как понимать вопрос:", ambiguities=request_items
        )
        return {
            "route": "clarify",
            "pending_clarification": {
                "request": request.model_dump(mode="json"),
                "interpretations": interpretations,
                "spans": spans,
            },
            "_detail": verdict.reason,
        }

    @step("clarify")
    async def clarify(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        pending = state["pending_clarification"]
        assert pending is not None
        # граф останавливается здесь; ответ приходит через Command(resume=answers)
        answers: list[dict[str, Any]] = interrupt(pending["request"])
        request = ClarificationRequest.model_validate(pending["request"])
        labels = {o.id: o.label for a in request.ambiguities for o in a.options}
        chosen: list[Clarification] = []
        for answer in answers:
            aid, oid = answer["ambiguity_id"], answer.get("option_id")
            span = pending["spans"].get(aid, aid)
            if oid and oid in pending["interpretations"]:
                chosen.append(
                    Clarification(
                        span=span,
                        choice=labels[oid],
                        interpretation=pending["interpretations"][oid],
                    )
                )
            elif text := (answer.get("free_text") or "").strip():
                chosen.append(Clarification(span=span, choice=text, interpretation=text))
        turn = [*state.get("turn_clarifications", []), *chosen]
        resolved = state["question"]
        if turn:
            resolved += "\n\n" + clarifications_text(turn, "Уточнения пользователя")
        return {
            "turn_clarifications": turn,
            "clarifications": chosen,
            "clarification_rounds": state.get("clarification_rounds", 0) + 1,
            "pending_clarification": None,
            "resolved_question": resolved,
            "_detail": "; ".join(f"{c['span']} → {c['choice']}" for c in chosen),
        }

    @step("generate_sql")
    async def generate_sql(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        context = runtime.context
        examples = "\n\n".join(
            f"Вопрос: {e['question']}\nSQL:\n{e['sql']}" for e in state.get("examples", [])
        )
        errors = "\n\n".join(
            f"Попытка {i}:\n{f['sql']}\nОшибка (уровень {f['level']}): {f['message']}"
            + (f"\nПодсказка: {f['hint']}" if f["hint"] else "")
            for i, f in enumerate(state.get("feedback", []), 1)
        )
        user = "\n\n".join(
            part
            for part in (
                f"<schema>\n{state['linked_schema']}\n</schema>",
                f"<examples>\n{examples}\n</examples>" if examples else "",
                dialog_context(state),
                f"<previous_errors>\n{errors}\n</previous_errors>" if errors else "",
                f"Вопрос: {state['resolved_question']}",
            )
            if part
        )
        generated = await self._structured(
            "generate_sql", "generate_sql", user, GeneratedSQL, config,
            today=context.today.isoformat(), timezone=context.snapshot.timezone or "UTC",
        )  # fmt: skip
        attempt = state.get("attempts", 0) + 1
        sql = generated.sql.strip().rstrip(";").strip()
        if not sql:
            return refusal(
                "cannot_answer", generated.explanation or "Не могу ответить по этой базе."
            )
        emit("sql", SqlEvent(sql=sql, attempt=attempt))
        return {"sql": sql, "attempts": attempt, "route": "validate"}

    def _retry_or_give_up(self, state: AgentState, failed: ValidationLevelResult) -> Update:
        feedback = Feedback(
            sql=state["sql"] or "",
            level=failed.level,
            message=failed.message or "",
            hint=failed.hint,
        )
        if state.get("attempts", 0) >= self.max_attempts:
            return {**refusal("max_attempts"), "feedback": [*state.get("feedback", []), feedback]}
        return {"route": "retry", "feedback": [*state.get("feedback", []), feedback]}

    @step("validate_sql")
    async def validate_sql(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        context = runtime.context
        report = validate(
            state["sql"] or "", context.snapshot, context.limits, schema_check=self.semantic_checks
        )
        for level in report.levels:
            emit("validation", level)
        failed = next((lv for lv in report.levels if not lv.passed), None)
        if failed is not None:
            if failed.fatal:
                return refusal("unsafe_sql")
            return self._retry_or_give_up(state, failed)

        assert report.normalized_sql is not None
        if context.pool is None:
            return refusal("no_connection")
        if self.semantic_checks:
            async with context.pool.acquire() as conn:
                plan = await explain(report.normalized_sql, conn, context.limits)
            emit("validation", plan)
            if not plan.passed:
                return self._retry_or_give_up(state, plan)
        return {"route": "execute", "normalized_sql": report.normalized_sql}

    @step("self_correct")
    async def self_correct(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        last = state["feedback"][-1]
        return {"_detail": f"Уровень {last['level']}: {last['message']}"}

    @step("execute")
    async def execute(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        context = runtime.context
        assert context.pool is not None and state["normalized_sql"]
        try:
            async with context.pool.acquire() as conn:
                result = await execute_readonly(state["normalized_sql"], conn, context.limits)
        except ExecutionError as e:
            emit("validation", e.result)
            return self._retry_or_give_up(state, e.result)
        emit(
            "validation",
            ValidationLevelResult(
                level=5,
                name="execution",
                passed=True,
                message=f"Выполнено за {result.duration_ms} мс, строк: {result.row_count}",
            ),
        )
        emit("result", result)
        return {"route": "explain", "result": result.model_dump(mode="json")}

    @step("explain_and_visualize")
    async def explain_and_visualize(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        result = QueryResult.model_validate(state["result"])
        chart = choose_chart(result)
        if chart is not None:
            emit("chart", chart)
        if not self.explain_enabled:
            return {
                "answer": "",
                "chart": chart.model_dump(mode="json") if chart else None,
                "history": [
                    Turn(question=state["question"], sql=state["normalized_sql"], answer="")
                ],
            }

        payload = {
            "columns": [c.name for c in result.columns],
            "rows": result.rows[:50],
            "row_count": result.row_count,
            "truncated": result.truncated,
        }
        user = "\n\n".join(
            part
            for part in (
                f"Вопрос: {state['question']}",
                clarifications_text(state.get("turn_clarifications", []), "Уточнения"),
                f"SQL:\n{state['normalized_sql']}",
                "<query_result>\n"
                + json.dumps(payload, ensure_ascii=False, default=str)
                + "\n</query_result>",
            )
            if part
        )
        messages, extra = self._messages("explain", user)
        chunks = []
        async for chunk in self.llm.stream_text("explain", messages, self._config(config, extra)):
            chunks.append(chunk)
            emit("answer", AnswerEvent(text=chunk))
        answer = "".join(chunks).strip()
        if suspicious := ungrounded_numbers(answer, result):
            log.warning("answer_numbers_not_in_result", numbers=suspicious)
        return {
            "answer": answer,
            "chart": chart.model_dump(mode="json") if chart else None,
            "history": [
                Turn(question=state["question"], sql=state["normalized_sql"], answer=answer)
            ],
        }

    @step("refuse")
    async def refuse(
        self, state: AgentState, runtime: Runtime[AgentContext], config: RunnableConfig
    ) -> Update:
        error = state.get("error") or {"code": "refused", "message": REFUSALS["refused"]}
        emit("error", ErrorEvent(code=error["code"], message=error["message"]))
        return {
            "answer": error["message"],
            "history": [Turn(question=state["question"], sql=state.get("sql"), answer=None)],
            "_detail": error["code"],
        }
