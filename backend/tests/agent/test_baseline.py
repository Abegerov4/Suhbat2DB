from app.agent.baseline import BaselineResult, BaselineRunner
from app.agent.prompts import PromptRegistry
from app.agent.state import AgentContext
from app.core.config import get_settings
from tests.agent.conftest import GOOD_SQL, FakeLLM, sql
from tests.conftest import requires_db

pytestmark = requires_db


async def answer(llm: FakeLLM, context: AgentContext) -> BaselineResult:
    return await BaselineRunner(llm, PromptRegistry(get_settings())).answer("вопрос", context)


async def test_baseline_executes_with_full_schema(agent_context: AgentContext) -> None:
    llm = FakeLLM(generate_sql=[sql(GOOD_SQL + ";")])
    result = await answer(llm, agent_context)
    assert result.result is not None and result.result.row_count == 5
    prompt = llm.prompts("generate_sql")[0]
    assert all(f"TABLE public.{t}" in prompt for t in ("regions", "orders", "events"))


async def test_baseline_has_no_self_correction(agent_context: AgentContext) -> None:
    result = await answer(FakeLLM(generate_sql=[sql("SELECT nope FROM orders")]), agent_context)
    assert result.result is None and "nope" in (result.error or "")


async def test_baseline_keeps_safety(agent_context: AgentContext) -> None:
    for bad in ("DELETE FROM orders", "SELECT 1; DROP TABLE orders"):
        result = await answer(FakeLLM(generate_sql=[sql(bad)]), agent_context)
        assert result.blocked
    empty = await answer(FakeLLM(generate_sql=[sql("")]), agent_context)
    assert empty.error == "пустой SQL"
    broken = await answer(FakeLLM(generate_sql=[sql("SELEC 1")]), agent_context)
    assert not broken.blocked and broken.error
