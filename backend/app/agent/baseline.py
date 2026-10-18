"""Базовый подход для сравнения (эксперимент 1): SQL одним вызовом LLM по полной схеме.

Без schema linking, уточнений, few-shot, сверки со схемой и самокоррекции. Из проверок
оставлены только политика «только чтение» (уровень 2) и изолированное выполнение
(уровень 5) — чтобы эксперимент не мог испортить данные.
"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent.llm import LLM
from app.agent.nodes import GeneratedSQL
from app.agent.prompts import PromptRegistry
from app.agent.retrieval.linker import full_schema
from app.agent.state import AgentContext
from app.schemas.agent import QueryResult
from app.validator import ExecutionError, execute_readonly
from app.validator.policy import check_policy
from app.validator.syntax import check_syntax


@dataclass
class BaselineResult:
    sql: str | None
    result: QueryResult | None = None
    blocked: bool = False
    error: str | None = None


@dataclass
class BaselineRunner:
    llm: LLM
    prompts: PromptRegistry

    async def answer(
        self, question: str, context: AgentContext, config: RunnableConfig | None = None
    ) -> BaselineResult:
        prompt = self.prompts.get("baseline")
        system = prompt.compile(
            today=context.today.isoformat(), timezone=context.snapshot.timezone or "UTC"
        )
        user = (
            f"<schema>\n{full_schema(context.snapshot).render()}\n</schema>\n\nВопрос: {question}"
        )
        generated = await self.llm.structured(
            "generate_sql", [SystemMessage(system), HumanMessage(user)], GeneratedSQL, config
        )
        sql = generated.sql.strip().rstrip(";").strip()
        if not sql:
            return BaselineResult(sql=None, error="пустой SQL")

        syntax, expression = check_syntax(sql)
        if expression is None:
            return BaselineResult(sql=sql, error=syntax.message, blocked=syntax.fatal)
        policy = check_policy(expression)
        if not policy.passed:
            return BaselineResult(sql=sql, error=policy.message, blocked=True)

        assert context.pool is not None
        try:
            async with context.pool.acquire() as conn:
                result = await execute_readonly(sql, conn, context.limits)
        except ExecutionError as e:
            return BaselineResult(sql=sql, error=e.result.message)
        return BaselineResult(sql=sql, result=result)
