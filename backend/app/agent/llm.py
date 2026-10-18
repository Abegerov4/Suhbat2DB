"""Слой LLM: модель на узел, structured output, резервный провайдер.

Узлы графа зависят только от интерфейса LLM — в тестах подставляется сценарий
ответов (FakeLLM), в работе — LangChainLLM с OpenAI/Anthropic.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel

from app.core.config import Settings

T = TypeVar("T", bound=BaseModel)

Tier = Literal["strong", "fast"]
NodeKey = Literal["guard", "ambiguity", "generate_sql", "explain"]


@dataclass(frozen=True)
class NodeConfig:
    tier: Tier
    temperature: float
    max_tokens: int


# Обоснование — docs/roles/05_ai_agent.md §5.1: точность важнее разнообразия везде,
# кроме формулировки пояснения
NODE_CONFIG: dict[NodeKey, NodeConfig] = {
    "guard": NodeConfig("fast", 0.0, 300),
    "ambiguity": NodeConfig("strong", 0.0, 1200),
    "generate_sql": NodeConfig("strong", 0.0, 1500),
    "explain": NodeConfig("fast", 0.3, 600),
}


class LLM(Protocol):
    async def structured(
        self,
        node: NodeKey,
        messages: list[BaseMessage],
        schema: type[T],
        config: RunnableConfig | None = None,
    ) -> T: ...

    def stream_text(
        self, node: NodeKey, messages: list[BaseMessage], config: RunnableConfig | None = None
    ) -> AsyncIterator[str]: ...

    def model_name(self, node: NodeKey) -> str: ...


def supports_temperature(model: str) -> bool:
    # рассуждающие модели OpenAI (o-серия, gpt-5*) принимают только значение по умолчанию
    return not model.startswith(("o1", "o3", "o4", "gpt-5"))


class LangChainLLM:
    def __init__(self, settings: Settings, overrides: dict[NodeKey, str] | None = None) -> None:
        self.settings = settings
        self.overrides = overrides or {}
        providers = [settings.llm_primary_provider]
        if settings.llm_fallback_provider and settings.llm_fallback_provider not in providers:
            providers.append(settings.llm_fallback_provider)
        self.providers = [p for p in providers if self._has_key(p)]
        if not self.providers:
            raise RuntimeError("Не задан ключ ни одного LLM-провайдера (OPENAI_API_KEY и т.п.)")

    def _has_key(self, provider: str) -> bool:
        key = (
            self.settings.openai_api_key
            if provider == "openai"
            else self.settings.anthropic_api_key
        )
        return key is not None and bool(key.get_secret_value())

    def _model_id(self, provider: str, node: NodeKey) -> str:
        if node in self.overrides and provider == self.providers[0]:
            return self.overrides[node]
        tier = NODE_CONFIG[node].tier
        s = self.settings
        if provider == "openai":
            return s.llm_openai_strong if tier == "strong" else s.llm_openai_fast
        return s.llm_anthropic_strong if tier == "strong" else s.llm_anthropic_fast

    def model_name(self, node: NodeKey) -> str:
        return self._model_id(self.providers[0], node)

    def _chat(self, provider: str, node: NodeKey) -> BaseChatModel:
        cfg, model = NODE_CONFIG[node], self._model_id(provider, node)
        temperature = cfg.temperature if supports_temperature(model) else None
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            assert self.settings.openai_api_key is not None
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                max_completion_tokens=cfg.max_tokens,
                timeout=self.settings.llm_timeout_s,
                max_retries=2,
                api_key=self.settings.openai_api_key,
            )
        from langchain_anthropic import ChatAnthropic

        assert self.settings.anthropic_api_key is not None
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=cfg.max_tokens,
            timeout=self.settings.llm_timeout_s,
            max_retries=2,
            api_key=self.settings.anthropic_api_key,
        )

    def _with_fallbacks(self, runnables: list[Runnable[Any, Any]]) -> Runnable[Any, Any]:
        primary, *rest = runnables
        return primary.with_fallbacks(rest) if rest else primary

    async def structured(
        self,
        node: NodeKey,
        messages: list[BaseMessage],
        schema: type[T],
        config: RunnableConfig | None = None,
    ) -> T:
        runnable = self._with_fallbacks(
            [self._chat(p, node).with_structured_output(schema) for p in self.providers]
        )
        result = await runnable.ainvoke(messages, config=_named(config, node))
        assert isinstance(result, schema)
        return result

    async def stream_text(
        self, node: NodeKey, messages: list[BaseMessage], config: RunnableConfig | None = None
    ) -> AsyncIterator[str]:
        runnable = self._with_fallbacks([self._chat(p, node) for p in self.providers])
        async for chunk in runnable.astream(messages, config=_named(config, node)):
            text = chunk.content if isinstance(chunk.content, str) else ""
            if text:
                yield text


def _named(config: RunnableConfig | None, node: str) -> RunnableConfig:
    """Имя узла в трассе Langfuse вместо безликого ChatOpenAI."""
    named: RunnableConfig = dict(config or {})  # type: ignore[assignment]
    named["run_name"] = f"llm:{node}"
    return named
