"""Граф целиком: сценарная LLM, настоящие валидатор, тестовая целевая БД и Qdrant в памяти."""

from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.types import Command

from app.agent.retrieval.store import SchemaStore
from app.agent.state import AgentContext, new_turn
from tests.agent.conftest import GOOD_SQL, FakeLLM, make_graph, of_type, run, sql
from tests.conftest import requires_db

pytestmark = requires_db


async def test_happy_path(store: SchemaStore, agent_context: AgentContext) -> None:
    llm = FakeLLM(generate_sql=[sql(GOOD_SQL)])
    graph = make_graph(llm, store)
    events, interrupted = await run(graph, new_turn("Сумма заказов по регионам"), agent_context)

    assert interrupted is None
    steps = [d["node"] for d in of_type(events, "step") if d["status"] == "finished"]
    assert steps == [
        "guard_input", "schema_linking", "detect_ambiguity", "generate_sql", "validate_sql",
        "execute", "explain_and_visualize",
    ]  # fmt: skip
    assert [v["level"] for v in of_type(events, "validation")] == [1, 2, 3, 4, 5]
    assert all(v["passed"] for v in of_type(events, "validation"))
    [result] = of_type(events, "result")
    assert result["row_count"] == 5
    assert of_type(events, "chart")[0]["type"] in ("bar", "pie")
    assert "".join(a["text"] for a in of_type(events, "answer")) == "Результат готов."

    # в промпт генератора попали связанная схема и few-shot не из чужой БД
    [prompt] = llm.prompts("generate_sql")
    assert "TABLE public.orders" in prompt and "<examples>" not in prompt
    state = (await graph.aget_state({"configurable": {"thread_id": "t1"}})).values
    assert state["history"][-1]["sql"].endswith("LIMIT 1001")


async def test_self_correction_passes_hint(store: SchemaStore, agent_context: AgentContext) -> None:
    llm = FakeLLM(generate_sql=[sql("SELECT sum(o.total) FROM orders o"), sql(GOOD_SQL)])
    events, _ = await run(make_graph(llm, store), new_turn("Сумма заказов"), agent_context)

    attempts = [s["attempt"] for s in of_type(events, "sql")]
    assert attempts == [1, 2]
    assert "self_correct" in [d["node"] for d in of_type(events, "step")]
    second = llm.prompts("generate_sql")[1]
    assert "Ошибка (уровень 3)" in second
    assert "Подсказка: Столбцы orders: id, region_id, status, amount" in second  # подсказка дошла
    assert of_type(events, "result")


async def test_runtime_error_triggers_retry(
    store: SchemaStore, agent_context: AgentContext
) -> None:
    bad = "SELECT 1 / (count(*) - count(*)) AS x FROM orders"
    llm = FakeLLM(generate_sql=[sql(bad), sql(GOOD_SQL)])
    events, _ = await run(make_graph(llm, store), new_turn("x"), agent_context)
    failed = [v for v in of_type(events, "validation") if not v["passed"]]
    assert failed[0]["level"] == 5 and "division by zero" in failed[0]["message"]
    assert of_type(events, "result")


async def test_gives_up_after_max_attempts(store: SchemaStore, agent_context: AgentContext) -> None:
    llm = FakeLLM(generate_sql=[sql("SELECT nope FROM orders")])
    events, _ = await run(make_graph(llm, store, max_attempts=3), new_turn("x"), agent_context)
    assert len(of_type(events, "sql")) == 3
    assert of_type(events, "error")[0]["code"] == "max_attempts"


async def test_unsafe_sql_is_refused_without_retry(
    store: SchemaStore, agent_context: AgentContext
) -> None:
    llm = FakeLLM(generate_sql=[sql("DELETE FROM orders")])
    events, _ = await run(make_graph(llm, store), new_turn("x"), agent_context)
    assert len(of_type(events, "sql")) == 1
    assert of_type(events, "error")[0]["code"] == "unsafe_sql"
    assert not of_type(events, "result")


async def test_guard_refuses_modification(store: SchemaStore, agent_context: AgentContext) -> None:
    llm = FakeLLM(guard=[{"decision": "modify", "reason": "просит удалить"}])
    events, _ = await run(make_graph(llm, store), new_turn("Удали заказы"), agent_context)
    assert of_type(events, "error")[0]["code"] == "refused"
    assert [n for n, _ in llm.calls] == ["guard"]  # дальше граф не пошёл


async def test_out_of_scope_and_cannot_answer(
    store: SchemaStore, agent_context: AgentContext
) -> None:
    llm = FakeLLM(ambiguity=[{"status": "out_of_scope", "ambiguities": [], "reason": "погода"}])
    events, _ = await run(make_graph(llm, store), new_turn("Какая погода?"), agent_context)
    assert of_type(events, "error")[0]["code"] == "out_of_scope"

    llm = FakeLLM(generate_sql=[{"sql": "", "explanation": "В базе нет данных о погоде"}])
    events, _ = await run(make_graph(llm, store), new_turn("x"), agent_context, thread="t2")
    error = of_type(events, "error")[0]
    assert error == {"code": "cannot_answer", "message": "В базе нет данных о погоде"}


AMBIGUOUS = {
    "status": "ambiguous",
    "reason": "продажи",
    "ambiguities": [
        {
            "type": "metric",
            "span": "продажи",
            "options": [
                {
                    "label": "Выручка",
                    "description": "сумма",
                    "interpretation": "sum(orders.amount)",
                },
                {"label": "Число заказов", "description": "", "interpretation": "count(orders.id)"},
            ],
        },
        {
            "type": "scope",
            "span": "лишнее",
            "options": [{"label": "один", "description": "", "interpretation": "x"}],
        },
    ],
}


def expect_clarification(messages: list[BaseMessage]) -> dict[str, Any]:
    assert "sum(orders.amount)" not in str(messages[-1].content)
    return AMBIGUOUS


async def test_clarification_interrupt_and_resume(
    store: SchemaStore, agent_context: AgentContext
) -> None:
    llm = FakeLLM(
        ambiguity=[expect_clarification, {"status": "clear", "ambiguities": [], "reason": "ok"}],
        generate_sql=[sql(GOOD_SQL)],
    )
    graph = make_graph(llm, store)
    events, interrupted = await run(graph, new_turn("Продажи по регионам"), agent_context)

    assert interrupted is not None
    assert not of_type(events, "sql")
    [ambiguity] = interrupted["ambiguities"]  # вариант с одной опцией отброшен
    assert ambiguity["id"] == "a1" and [o["id"] for o in ambiguity["options"]] == ["a1o1", "a1o2"]

    answers = [{"ambiguity_id": "a1", "option_id": "a1o1", "free_text": None}]
    events, interrupted = await run(graph, Command(resume=answers), agent_context)
    assert interrupted is None and of_type(events, "result")
    prompt = llm.prompts("generate_sql")[0]
    assert "продажи: Выручка → sum(orders.amount)" in prompt

    # память сессии: следующий вопрос видит прошлое уточнение
    await run(graph, new_turn("А по месяцам?"), agent_context)
    assert "Прошлые уточнения" in llm.prompts("ambiguity")[-1]
    assert "Продажи по регионам" in llm.prompts("generate_sql")[-1]  # контекст диалога


async def test_clarification_rounds_are_limited(
    store: SchemaStore, agent_context: AgentContext
) -> None:
    llm = FakeLLM(ambiguity=[AMBIGUOUS], generate_sql=[sql(GOOD_SQL)])
    graph = make_graph(llm, store, max_clarification_rounds=1)
    _, interrupted = await run(graph, new_turn("Продажи"), agent_context)
    assert interrupted is not None
    free = [{"ambiguity_id": "a1", "option_id": None, "free_text": "выручка без возвратов"}]
    _events, interrupted = await run(graph, Command(resume=free), agent_context)
    assert interrupted is None  # второй раунд не запрашивается, хотя LLM снова «сомневается»
    assert "выручка без возвратов" in llm.prompts("generate_sql")[0]
