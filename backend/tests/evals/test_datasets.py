"""Состав и формат наборов: требования docs/roles/07_evals.md проверяются автоматически."""

from collections import Counter
from typing import Any

import pytest
from sqlglot import parse_one

from evals.build_benchmarks import to_postgres
from evals.config import load_config
from evals.datasets import load_suite, stratified
from evals.hardness import hardness


def test_benchmark_subsets_are_stratified() -> None:
    spider = load_suite("spider_subset")
    bird = load_suite("bird_subset")
    assert Counter(c.difficulty for c in spider) == {
        "easy": 50,
        "medium": 50,
        "hard": 50,
        "extra": 50,
    }
    assert Counter(c.difficulty for c in bird) == {"simple": 50, "moderate": 50, "challenging": 50}
    for case in spider + bird:
        parse_one(case.gold_sql or "", dialect="postgres")  # эталон — валидный PostgreSQL
        assert case.database.startswith(("spider_", "bird_"))
    assert any("\nHint: " in c.question for c in bird)  # evidence BIRD передаётся агенту


def test_ambiguous_ru_requirements() -> None:
    cases = load_suite("ambiguous_ru")
    amb = [c for c in cases if c.is_ambiguous]
    clear = [c for c in cases if not c.is_ambiguous]
    assert len(amb) >= 60 and len(clear) >= 40
    for c in amb:
        assert 2 <= len(c.interpretations) <= 4 and 0 <= c.target < len(c.interpretations)
        assert all(i["answer_to_clarification"] for i in c.interpretations)
        assert c.ambiguity_types
    assert all(len(c.interpretations) == 1 for c in clear)
    # задуманная трактовка не всегда первая — иначе «угадывание по умолчанию» завышало бы EX
    assert len({c.target for c in amb}) > 1
    types = Counter(t for c in amb for t in c.ambiguity_types)
    assert set(types) == {"metric", "temporal", "value", "scope", "schema"}


def test_unsafe_requirements() -> None:
    cases = load_suite("unsafe")
    agent = [c for c in cases if c.sql is None]
    attacks = [c for c in agent if c.expected in ("block", "contain")]
    benign = [c for c in agent if c.kind == "benign"]
    assert len(attacks) >= 50 and len(benign) >= 30
    assert {c.lang for c in attacks} >= {"ru", "kk", "mixed", "en"}
    assert {c.kind for c in agent} >= {"modify", "injection", "exfiltration", "heavy", "indirect"}
    assert all(c.canaries and c.database == "eval_poisoned" for c in agent if c.kind == "indirect")
    assert all(c.expected == "contain" for c in agent if c.kind == "heavy")
    assert sum(1 for c in cases if c.sql is not None) == 88 + 42  # SQL-атаки роли 4


def test_stratified_is_deterministic_and_proportional() -> None:
    cases = load_suite("spider_subset")
    a, b = stratified(cases, 20, seed=0), stratified(cases, 20, seed=0)
    assert [c.id for c in a] == [c.id for c in b] and len(a) == 20
    assert Counter(c.difficulty for c in a) == {"easy": 5, "medium": 5, "hard": 5, "extra": 5}
    assert stratified(cases, 1000) == cases


def test_to_postgres() -> None:
    names = {"singer", "language", "name", "country"}
    sql = to_postgres(
        'SELECT T1.Name FROM singer AS T1 WHERE language = "English" AND "Country" = 1', names
    )
    assert "'English'" in sql  # SQLite: строка в двойных кавычках
    assert "t1.name" in sql and "country = 1" in sql  # простые имена — в нижнем регистре
    assert "DOUBLE PRECISION" in to_postgres("SELECT CAST(a AS REAL) FROM t")
    assert '"Free Meal Count (K-12)"' in to_postgres("SELECT `Free Meal Count (K-12)` FROM frpm")


def test_spider_hardness_examples() -> None:
    empty_from = {"table_units": [("table_unit", 0)], "conds": []}
    base: dict[str, Any] = {
        "select": (False, [(0, (0, (0, 1, False), None))]),
        "from": empty_from,
        "where": [],
        "groupBy": [],
        "orderBy": [],
        "having": [],
        "limit": None,
        "intersect": None,
        "union": None,
        "except": None,
    }
    assert hardness(base) == "easy"
    two_cols: dict[str, Any] = {
        **base,
        "select": (False, [(0, None), (0, None)]),
        "orderBy": ("asc", []),
    }
    assert hardness({**two_cols, "orderBy": ("desc", [(0, (0, 1, False), None)])}) == "medium"
    nested = {**base, "union": base}
    assert hardness(nested) == "hard"


def test_configs_load() -> None:
    assert load_config("agent").system == "agent"
    assert load_config("baseline").system == "baseline"
    assert load_config("agent_mini").models["generate_sql"] == "gpt-4.1-mini"
    assert load_config("agent_t07").temperatures["generate_sql"] == 0.7
    with pytest.raises(SystemExit):
        load_config("nope")
