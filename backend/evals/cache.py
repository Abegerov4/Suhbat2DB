"""Кэш ответов LLM и учёт токенов для evals.

Ключ — хэш (узел, модель, temperature, seed, схема ответа, сообщения). Повторный прогон
тех же конфигураций не обращается к API: пересчёт метрик бесплатный и детерминированный.
Вместе с ответом хранится расход токенов исходного вызова — стоимость в отчёте не
зависит от того, попал ли вызов в кэш.
"""

import hashlib
import json
import sqlite3
import threading
from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from langchain_core.callbacks import BaseCallbackHandler, BaseCallbackManager
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from app.agent.llm import NODE_CONFIG, LangChainLLM, NodeKey

T = TypeVar("T", bound=BaseModel)

# USD за 1 млн токенов (прайс OpenAI на октябрь 2026), вход / выход
PRICES: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def price_of(model: str) -> tuple[float, float]:
    for prefix in sorted(PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return PRICES[prefix]
    return (0.0, 0.0)


@dataclass
class Usage:
    """Токены и вызовы одного вопроса (по моделям)."""

    tokens: dict[str, list[int]] = field(default_factory=dict)  # модель → [вход, выход]
    calls: int = 0
    cached_calls: int = 0

    def add(self, model: str, prompt: int, completion: int) -> None:
        t = self.tokens.setdefault(model, [0, 0])
        t[0] += prompt
        t[1] += completion

    @property
    def cost_usd(self) -> float:
        total = 0.0
        for model, (p, c) in self.tokens.items():
            pin, pout = price_of(model)
            total += p / 1e6 * pin + c / 1e6 * pout
        return total

    def as_dict(self) -> dict[str, Any]:
        return {
            "tokens": self.tokens,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "cost_usd": round(self.cost_usd, 6),
        }


current_usage: ContextVar[Usage | None] = ContextVar("current_usage", default=None)


class UsageCallback(BaseCallbackHandler):
    """Собирает расход токенов одного вызова модели из ответа LangChain."""

    def __init__(self) -> None:
        self.usage = Usage()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for generations in response.generations:
            for gen in generations:
                message = getattr(gen, "message", None)
                meta = getattr(message, "usage_metadata", None) or {}
                model = (getattr(message, "response_metadata", None) or {}).get("model_name", "")
                if meta:
                    self.usage.add(
                        model or "unknown",
                        meta.get("input_tokens", 0),
                        meta.get("output_tokens", 0),
                    )


class LLMCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS llm (key TEXT PRIMARY KEY, value TEXT, usage TEXT)"
        )
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[str, dict[str, list[int]]] | None:
        with self._lock:
            row = self._con.execute("SELECT value, usage FROM llm WHERE key = ?", (key,)).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def put(self, key: str, value: str, usage: dict[str, list[int]]) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO llm VALUES (?, ?, ?)", (key, value, json.dumps(usage))
            )
            self._con.commit()


class CachedLLM:
    """LLM для evals: кэш + учёт токенов поверх LangChainLLM (реализует протокол LLM)."""

    def __init__(self, inner: LangChainLLM, cache: LLMCache) -> None:
        self.inner = inner
        self.cache = cache

    def model_name(self, node: NodeKey) -> str:
        return self.inner.model_name(node)

    def _key(self, node: NodeKey, messages: list[BaseMessage], schema: str) -> str:
        model = self.inner.model_name(node)
        payload = {
            "node": node,
            "model": model,
            "temperature": self.inner.temperatures.get(node, NODE_CONFIG[node].temperature),
            "seed": self.inner.seed,
            "schema": schema,
            "messages": [(m.type, m.content) for m in messages],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _track(self, tokens: dict[str, list[int]], cached: bool) -> None:
        usage = current_usage.get()
        if usage is None:
            return
        usage.calls += 1
        usage.cached_calls += int(cached)
        for model, (p, c) in tokens.items():
            usage.add(model, p, c)

    @staticmethod
    def _with_callback(config: RunnableConfig | None, cb: UsageCallback) -> RunnableConfig:
        merged: RunnableConfig = dict(config or {})  # type: ignore[assignment]
        current = merged.get("callbacks")
        if isinstance(current, BaseCallbackManager):  # внутри графа LangGraph — менеджер
            manager = current.copy()
            manager.add_handler(cb, inherit=True)
            merged["callbacks"] = manager
        else:
            merged["callbacks"] = [*(current or []), cb]
        return merged

    async def structured(
        self,
        node: NodeKey,
        messages: list[BaseMessage],
        schema: type[T],
        config: RunnableConfig | None = None,
    ) -> T:
        key = self._key(node, messages, json.dumps(schema.model_json_schema(), sort_keys=True))
        if (hit := self.cache.get(key)) is not None:
            self._track(hit[1], cached=True)
            return schema.model_validate_json(hit[0])
        cb = UsageCallback()
        result = await self.inner.structured(
            node, messages, schema, self._with_callback(config, cb)
        )
        self.cache.put(key, result.model_dump_json(), cb.usage.tokens)
        self._track(cb.usage.tokens, cached=False)
        return result

    async def stream_text(
        self, node: NodeKey, messages: list[BaseMessage], config: RunnableConfig | None = None
    ) -> AsyncIterator[str]:
        key = self._key(node, messages, "text")
        if (hit := self.cache.get(key)) is not None:
            self._track(hit[1], cached=True)
            yield hit[0]
            return
        cb = UsageCallback()
        chunks = []
        async for chunk in self.inner.stream_text(node, messages, self._with_callback(config, cb)):
            chunks.append(chunk)
            yield chunk
        self.cache.put(key, "".join(chunks), cb.usage.tokens)
        self._track(cb.usage.tokens, cached=False)
