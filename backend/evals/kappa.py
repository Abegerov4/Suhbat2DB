"""Проверка разметки ambiguous_ru вторым человеком (Cohen's κ).

1. export — случайные 20% вопросов (seed фиксирован) в случайном порядке → review_sample.csv.
   Второй разметчик НЕ видит разметку автора (ни id, ни трактовок): заполняет столбец
   reviewer_ambiguous (да / нет) и, если «да», — reviewer_types (metric, temporal, value,
   scope, schema через запятую).
2. score — согласованность по «неоднозначен / однозначен» и по типам.

    cd backend && uv run python -m evals.kappa export
    cd backend && uv run python -m evals.kappa score
"""

import argparse
import csv
import json
import random

from evals.datasets import load_suite
from evals.metrics import cohen_kappa
from evals.paths import DATASETS

DIR = DATASETS / "ambiguous_ru"
SAMPLE = DIR / "review_sample.csv"
RESULT = DIR / "review_result.json"
KEY = DIR / "review_key.json"  # номер строки → id: в id есть amb/clear, разметчик их не видит
SHARE = 0.2
SEED = 7
YES = {"да", "yes", "1", "true", "+"}


def export() -> None:
    cases = sorted(load_suite("ambiguous_ru"), key=lambda c: c.id)
    k = max(1, round(len(cases) * SHARE))
    sample = random.Random(SEED).sample(cases, k)  # случайный порядок, без группировки
    with SAMPLE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "question", "reviewer_ambiguous", "reviewer_types", "comment"])
        for n, c in enumerate(sample, 1):
            w.writerow([n, c.question, "", "", ""])
    KEY.write_text(
        json.dumps({str(n): c.id for n, c in enumerate(sample, 1)}, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{SAMPLE.relative_to(DATASETS.parent.parent)}: {k} вопросов для второго разметчика")


def score() -> None:
    author = {c.id: c for c in load_suite("ambiguous_ru")}
    key = json.loads(KEY.read_text(encoding="utf-8"))
    with SAMPLE.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["reviewer_ambiguous"].strip()]
    for r in rows:
        r["id"] = key[r["n"]]
    if not rows:
        raise SystemExit("review_sample.csv ещё не заполнен")
    a = [bool(author[r["id"]].is_ambiguous) for r in rows]
    b = [r["reviewer_ambiguous"].strip().lower() in YES for r in rows]
    both = [r for r in rows if author[r["id"]].is_ambiguous and r["reviewer_types"].strip()]
    type_agreement = [
        set(author[r["id"]].ambiguity_types)
        == {t.strip() for t in r["reviewer_types"].split(",") if t.strip()}
        for r in both
    ]
    result = {
        "n": len(rows),
        "kappa_is_ambiguous": cohen_kappa(a, b),
        "raw_agreement": round(sum(x == y for x, y in zip(a, b, strict=True)) / len(rows), 3),
        "type_exact_agreement": round(sum(type_agreement) / len(both), 3) if both else None,
        "disagreements": [r["id"] for r, x, y in zip(rows, a, b, strict=True) if x != y],
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "score"])
    args = parser.parse_args()
    export() if args.action == "export" else score()


if __name__ == "__main__":
    main()
