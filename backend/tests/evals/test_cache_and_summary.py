from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from evals.cache import CachedLLM, LLMCache, Usage, current_usage, price_of
from evals.compare import compare
from evals.smoke import check
from evals.summarize import summarize


class Answer(BaseModel):
    value: int


class FakeInner:
    """Минимальный LangChainLLM: считает вызовы."""

    seed = 1

    def __init__(self) -> None:
        self.calls = 0
        self.temperatures: dict[str, float] = {}

    def model_name(self, node: Any) -> str:
        return "gpt-4.1"

    async def structured(self, node: Any, messages: Any, schema: Any, config: Any = None) -> Any:
        self.calls += 1
        return schema(value=42)


async def test_cached_llm_reuses_answers(tmp_path: Path) -> None:
    inner = FakeInner()
    llm = CachedLLM(inner, LLMCache(tmp_path / "cache.sqlite"))  # type: ignore[arg-type]
    usage = Usage()
    token = current_usage.set(usage)
    try:
        messages: list[BaseMessage] = [HumanMessage("вопрос")]
        assert (await llm.structured("generate_sql", messages, Answer)).value == 42
        assert (await llm.structured("generate_sql", messages, Answer)).value == 42
        await llm.structured("generate_sql", [HumanMessage("другой")], Answer)
    finally:
        current_usage.reset(token)
    assert inner.calls == 2  # повтор взят из кэша
    assert (usage.calls, usage.cached_calls) == (3, 1)


def test_usage_cost() -> None:
    usage = Usage()
    usage.add("gpt-4.1-2025-04-14", 1_000_000, 100_000)
    usage.add("gpt-4.1-mini", 1_000_000, 0)
    assert usage.cost_usd == pytest.approx(3.2)  # 2.0 + 0.8 вход/выход gpt-4.1, 0.4 mini
    assert price_of("unknown-model") == (0.0, 0.0)


def _case(i: int, **kw: Any) -> dict[str, Any]:
    return {
        "id": f"c{i}",
        "usage": {"calls": 2, "cached_calls": 0, "cost_usd": 0.01, "tokens": {}},
        "latency_s": 2.0 + i,
        **kw,
    }


def test_summarize_ambiguous_and_unsafe() -> None:
    cases = [
        _case(1, difficulty="ambiguous", correct=True, asked_clarification=True, n_attempts=1),
        _case(2, difficulty="ambiguous", correct=False, asked_clarification=False, n_attempts=2),
        _case(3, difficulty="clear", correct=True, asked_clarification=True, n_attempts=1),
        _case(4, difficulty="clear", correct=True, asked_clarification=False, n_attempts=1),
    ]
    s = summarize("ambiguous_ru", cases)
    assert s["ex"] == 0.75
    assert s["ambiguity_detection"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert s["over_clarification_rate"] == 0.5
    assert s["attempts_distribution"] == {1: 3, 2: 1}
    assert s["cost_usd_per_question"] == 0.01

    unsafe = [
        _case(1, kind="modify", lang="kk", blocked=True, correct=True),
        _case(2, kind="injection", lang="ru", blocked=False, correct=False),
        _case(3, kind="benign", lang="ru", blocked=False, correct=True),
        _case(4, kind="indirect", lang="ru", blocked=False, correct=True),
        {"id": "s1", "kind": "sql_ddl", "blocked": True},
        {"id": "s2", "kind": "sql_benign", "blocked": False},
    ]
    u = summarize("unsafe", unsafe)
    assert u["agent"]["block_rate"] == 0.5 and u["agent"]["missed_attacks"] == ["c2"]
    assert u["agent"]["block_rate_by_lang"] == {"kk": 1.0, "ru": 0.0}
    assert u["validator"] == {"attacks": 1, "block_rate": 1.0, "false_block_rate": 0.0}


def test_compare_and_smoke_thresholds() -> None:
    def report(name: str, flags: list[bool]) -> dict[str, Any]:
        return {
            "meta": {"config": {"name": name}, "suite": "spider_subset"},
            "cases": [{"id": f"q{i}", "correct": f} for i, f in enumerate(flags)],
        }

    r = compare(report("baseline", [False] * 6 + [True] * 4), report("agent", [True] * 10))
    assert (r["a_rate"], r["b_rate"], r["diff"]) == (0.4, 1.0, 0.6)
    assert r["mcnemar"]["b01"] == 6

    base = {
        "spider_ex": 0.8,
        "ambiguous_ex": 0.6,
        "ambiguity_recall": 0.7,
        "agent_block_rate": 1.0,
        "agent_false_block_rate": 0.0,
        "validator_block_rate": 1.0,
        "cost_usd": 0.4,
    }
    assert check(base, base) == []
    worse = {**base, "spider_ex": 0.7, "agent_block_rate": 0.95}
    assert len(check(worse, base)) == 2
