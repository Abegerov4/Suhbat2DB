"""Таблицы для EVALS.md из JSON-отчётов (цифры в документе не переписываются вручную).

    cd backend && uv run python -m evals.report > ../evals/reports/tables.md

Берётся последний отчёт для каждой пары (набор, конфигурация) с seed 1.
"""

import json
from pathlib import Path
from typing import Any

from evals.compare import compare
from evals.paths import REPORTS


def latest(suite: str, config: str, seed: int = 1) -> dict[str, Any] | None:
    paths = sorted(REPORTS.glob(f"20*_{suite}_{config}_s{seed}.json"))
    if not paths:
        return None
    data: dict[str, Any] = json.loads(Path(paths[-1]).read_text(encoding="utf-8"))
    return data


def pct(x: float) -> str:
    return f"{100 * x:.1f}"


def ci(c: list[float]) -> str:
    return f"[{pct(c[0])}; {pct(c[1])}]"


def p_value(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def experiment1() -> list[str]:
    lines = [
        "| Набор | Сложность | n | Baseline EX, % | Агент EX, % | Агент EX ослабл., % |",
        "|---|---|---|---|---|---|",
    ]
    stats = []
    for suite in ("spider_subset", "bird_subset"):
        a, b = latest(suite, "baseline"), latest(suite, "agent")
        if not a or not b:
            continue
        sa, sb = a["summary"], b["summary"]
        for level, block in sb["by_difficulty"].items():
            base = sa["by_difficulty"].get(level, {})
            lines.append(
                f"| {suite} | {level} | {block['n']} | {pct(base.get('ex', 0))} | "
                f"{pct(block['ex'])} | {pct(block['ex_relaxed'])} |"
            )
        lines.append(
            f"| **{suite}** | **всего** | **{sb['n']}** | "
            f"**{pct(sa['ex'])}** {ci(sa['ex_ci95'])} | "
            f"**{pct(sb['ex'])}** {ci(sb['ex_ci95'])} | {pct(sb['ex_relaxed'])} |"
        )
        stats.append(compare(a, b))
    lines += [
        "",
        "| Набор | Разница EX (агент − baseline), п.п. | 95% CI "
        "| Агент лучше / хуже | p (Макнемар) |",
        "|---|---|---|---|---|",
    ]
    for r in stats:
        m = r["mcnemar"]
        lines.append(
            f"| {r['suite']} | {100 * r['diff']:+.1f} | [{100 * r['diff_ci95'][0]:+.1f}; "
            f"{100 * r['diff_ci95'][1]:+.1f}] | {m['b01']} / {m['b10']} | {p_value(m['p_value'])} |"
        )
    return lines


def agent_details() -> list[str]:
    lines = [
        "| Набор | EX 1-й попытки, % | Итоговый EX, % | Вклад самокоррекции, п.п. | "
        "Schema recall | Все таблицы найдены, % | $ / вопрос | p50, с | p95, с |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for suite in ("spider_subset", "bird_subset", "ambiguous_ru"):
        r = latest(suite, "agent")
        if not r:
            continue
        s = r["summary"]
        lines.append(
            f"| {suite} | {pct(s['first_attempt_ex'])} | {pct(s['ex'])} | "
            f"{100 * s['self_correction_gain']:+.1f} | {s.get('schema_recall', '—')} | "
            f"{pct(s['schema_full_recall']) if 'schema_full_recall' in s else '—'} | "
            f"{s.get('cost_usd_per_question', 0):.4f} | {s.get('latency_p50_s', '—')} | "
            f"{s.get('latency_p95_s', '—')} |"
        )
    base = [latest(s, "baseline") for s in ("spider_subset", "bird_subset")]
    for r in base:
        if r:
            s = r["summary"]
            lines.append(
                f"| {r['meta']['suite']} (baseline) | — | {pct(s['ex'])} | — | — | — | "
                f"{s.get('cost_usd_per_question', 0):.4f} | {s.get('latency_p50_s', '—')} | "
                f"{s.get('latency_p95_s', '—')} |"
            )
    return lines


def experiment2() -> list[str]:
    a, b = latest("ambiguous_ru", "agent_no_clarify"), latest("ambiguous_ru", "agent")
    if not a or not b:
        return ["(нет отчётов)"]
    sa, sb = a["summary"], b["summary"]
    det = sb["ambiguity_detection"]
    lines = [
        "| Метрика | Без уточнения | С уточнением |",
        "|---|---|---|",
        f"| EX на неоднозначных, % | {pct(sa['ex_ambiguous']['ex'])} "
        f"{ci(sa['ex_ambiguous']['ex_ci95'])} | {pct(sb['ex_ambiguous']['ex'])} "
        f"{ci(sb['ex_ambiguous']['ex_ci95'])} |",
        f"| EX на однозначных, % | {pct(sa['ex_clear']['ex'])} | {pct(sb['ex_clear']['ex'])} |",
        f"| EX на всём наборе, % | {pct(sa['ex'])} | {pct(sb['ex'])} |",
        f"| Precision / Recall / F1 поиска неоднозначности | — | "
        f"{det['precision']:.2f} / {det['recall']:.2f} / {det['f1']:.2f} |",
        f"| Лишние уточнения (over-clarification), % | — | {pct(sb['over_clarification_rate'])} |",
        f"| $ / вопрос | {sa.get('cost_usd_per_question', 0):.4f} | "
        f"{sb.get('cost_usd_per_question', 0):.4f} |",
    ]
    amb_a = {c["id"]: c for c in a["cases"] if c.get("difficulty") == "ambiguous"}
    amb_b = {c["id"]: c for c in b["cases"] if c.get("difficulty") == "ambiguous"}
    r = compare(
        {"meta": a["meta"], "cases": list(amb_a.values())},
        {"meta": b["meta"], "cases": list(amb_b.values())},
    )
    m = r["mcnemar"]
    lines += [
        "",
        f"На неоднозначных вопросах (n = {r['n']}): разница EX {100 * r['diff']:+.1f} п.п., "
        f"95% CI [{100 * r['diff_ci95'][0]:+.1f}; {100 * r['diff_ci95'][1]:+.1f}], "
        f"уточнение исправило {m['b01']} ответов и испортило {m['b10']}, "
        f"p (Макнемар) = {p_value(m['p_value'])}.",
    ]
    return lines


def security() -> list[str]:
    r = latest("unsafe", "agent")
    if not r:
        return ["(нет отчёта)"]
    a, v = r["summary"]["agent"], r["summary"]["validator"]
    lines = [
        "| Уровень | Атак | Заблокировано, % | Ложные блокировки, % |",
        "|---|---|---|---|",
        f"| Агент: вопросы на естественном языке | {a['attacks']} | {pct(a['block_rate'])} | "
        f"{pct(a['false_block_rate'])} (из {a['benign']}) |",
        f"| Валидатор: SQL-атаки | {v['attacks']} | {pct(v['block_rate'])} | "
        f"{pct(v['false_block_rate'])} |",
        "",
        "| Класс атак | Заблокировано, % |",
        "|---|---|",
    ]
    lines += [f"| {k} | {pct(x)} |" for k, x in a["block_rate_by_kind"].items()]
    lines += ["", "| Язык атак | Заблокировано, % |", "|---|---|"]
    lines += [f"| {k} | {pct(x)} |" for k, x in a["block_rate_by_lang"].items()]
    lines += [
        "",
        f"Непрямые инъекции через данные: устойчивость {pct(a['indirect_resisted'])}% "
        f"(n = {a['indirect']}); «тяжёлые» запросы удержаны лимитами: "
        f"{pct(a['heavy_contained'])}% (n = {a['heavy']}); попыток SQL, нарушающих политику "
        f"«только чтение», — {a['policy_violation_attempts']} (все остановлены уровнем 2).",
    ]
    if a["missed_attacks"] or a["false_blocks"]:
        lines.append(f"Пропущены: {a['missed_attacks']}; ложно заблокированы: {a['false_blocks']}.")
    return lines


def main() -> None:
    sections = (
        ("Эксперимент 1. Baseline против агента", experiment1),
        ("Агент: самокоррекция, отбор таблиц, стоимость", agent_details),
        ("Эксперимент 2. Уточнение неоднозначности", experiment2),
        ("Безопасность", security),
    )
    print("\n\n".join(f"### {title}\n\n" + "\n".join(section()) for title, section in sections))


if __name__ == "__main__":
    main()
