"""Парное сравнение двух прогонов на одних и тех же вопросах (эксперименты 1–5).

    cd backend && uv run python -m evals.compare REPORT_A.json REPORT_B.json [--metric correct]

Для EX — точный тест Макнемара по расхождениям и 95% парный bootstrap-интервал
разности B − A. Сравниваются только вопросы, которые есть в обоих отчётах.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from evals.metrics import mcnemar, paired_bootstrap_diff
from evals.paths import REPORTS


def load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        p = REPORTS / path
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    return data


def compare(a: dict[str, Any], b: dict[str, Any], metric: str = "correct") -> dict[str, Any]:
    ca = {c["id"]: c for c in a["cases"]}
    cb = {c["id"]: c for c in b["cases"]}
    ids = sorted(set(ca) & set(cb))
    xa = [bool(ca[i].get(metric)) for i in ids]
    xb = [bool(cb[i].get(metric)) for i in ids]
    n = len(ids)
    diff_ci = paired_bootstrap_diff([float(x) for x in xa], [float(x) for x in xb])
    return {
        "a": a["meta"]["config"]["name"],
        "b": b["meta"]["config"]["name"],
        "suite": a["meta"]["suite"],
        "metric": metric,
        "n": n,
        "a_rate": round(sum(xa) / n, 4) if n else 0.0,
        "b_rate": round(sum(xb) / n, 4) if n else 0.0,
        "diff": round((sum(xb) - sum(xa)) / n, 4) if n else 0.0,
        "diff_ci95": diff_ci,
        "mcnemar": mcnemar(xa, xb),
    }


def markdown(r: dict[str, Any]) -> str:
    m = r["mcnemar"]
    return (
        f"| {r['suite']} | {r['a']} | {r['b']} | {r['n']} | {r['a_rate']:.3f} | "
        f"{r['b_rate']:.3f} | {r['diff']:+.3f} [{r['diff_ci95'][0]:+.3f}; "
        f"{r['diff_ci95'][1]:+.3f}] | {m['b10']} / {m['b01']} | {m['p_value']} |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--metric", default="correct")
    args = parser.parse_args()
    result = compare(load(args.a), load(args.b), args.metric)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    print(markdown(result))


if __name__ == "__main__":
    main()
