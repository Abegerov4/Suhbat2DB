"""Наборы данных evals → единый формат EvalCase."""

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from evals.benchdb import database_name
from evals.paths import DATASETS

SUITES = ("spider_subset", "bird_subset", "ambiguous_ru", "unsafe")
DEMO = "demo"


@dataclass
class EvalCase:
    id: str
    suite: str
    database: str
    question: str
    gold_sql: str | None = None  # PostgreSQL
    difficulty: str | None = None
    # ambiguous_ru
    is_ambiguous: bool | None = None
    ambiguity_types: list[str] = field(default_factory=list)
    interpretations: list[dict[str, Any]] = field(default_factory=list)
    target: int = 0
    # unsafe
    kind: str | None = None
    lang: str | None = None
    expected: str | None = None  # block / allow
    canaries: list[str] = field(default_factory=list)
    sql: str | None = None  # SQL-атака уровня валидатора (без LLM)

    @property
    def intent(self) -> str:
        """Что «имел в виду» симулированный пользователь."""
        if self.interpretations:
            chosen = self.interpretations[self.target]
            return str(chosen.get("answer_to_clarification") or "как написано в вопросе")
        return f"Ответ должен совпадать с результатом этого SQL:\n{self.gold_sql}"


def _jsonl(path: str) -> list[dict[str, Any]]:
    text = (DATASETS / path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def load_suite(suite: str) -> list[EvalCase]:
    if suite in ("spider_subset", "bird_subset"):
        bench = suite.split("_")[0]
        cases = []
        for r in _jsonl(f"{suite}/{suite}.jsonl"):
            question = r["question"]
            if r.get("evidence"):  # BIRD: внешнее знание, как в стандартной постановке
                question += f"\nHint: {r['evidence']}"
            cases.append(
                EvalCase(
                    id=r["id"],
                    suite=suite,
                    database=database_name(bench, r["db_id"]),
                    question=question,
                    gold_sql=r["gold_sql"],
                    difficulty=r["difficulty"],
                )
            )
        return cases
    if suite == "ambiguous_ru":
        return [
            EvalCase(
                id=r["id"],
                suite=suite,
                database=DEMO,
                question=r["question"],
                gold_sql=r["interpretations"][r["target"]]["gold_sql"],
                is_ambiguous=r["is_ambiguous"],
                ambiguity_types=r["ambiguity_types"],
                interpretations=r["interpretations"],
                target=r["target"],
                difficulty="ambiguous" if r["is_ambiguous"] else "clear",
            )
            for r in _jsonl("ambiguous_ru/ambiguous_ru.jsonl")
        ]
    if suite == "unsafe":
        cases = [
            EvalCase(
                id=r["id"],
                suite=suite,
                database=r.get("db", DEMO),
                question=r["input"],
                kind=r["kind"],
                lang=r["lang"],
                expected=r["expected"],
                canaries=r.get("canaries", []),
            )
            for r in _jsonl("unsafe/questions.jsonl")
        ]
        for name in ("sql_attacks", "sql_benign"):
            for r in _jsonl(f"unsafe/{name}.jsonl"):
                cases.append(
                    EvalCase(
                        id=f"sql_{r['id']}",
                        suite=suite,
                        database=DEMO,
                        question="",
                        sql=r["sql"],
                        kind=f"sql_{r.get('category', 'benign')}",
                        expected=r["expected"],
                    )
                )
        return cases
    raise SystemExit(f"Неизвестный набор {suite!r}. Есть: {', '.join(SUITES)}")


def stratified(cases: list[EvalCase], limit: int, seed: int = 0) -> list[EvalCase]:
    """Подвыборка размера limit с сохранением долей групп (сложность / тип атаки)."""
    if limit >= len(cases):
        return cases
    groups: dict[str, list[EvalCase]] = defaultdict(list)
    for c in cases:
        groups[c.difficulty or c.kind or ""].append(c)
    rng = random.Random(seed)
    picked: list[EvalCase] = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda c: c.id)
        rng.shuffle(members)
        share = max(1, round(limit * len(members) / len(cases)))
        picked.extend(members[:share])
    rng.shuffle(picked)
    return sorted(picked[:limit], key=lambda c: c.id)
