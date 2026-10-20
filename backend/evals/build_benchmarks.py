"""Сборка spider_subset и bird_subset из dev-частей Spider 1.0 и BIRD.

1. Сложность: Spider — официальный eval_hardness (evals.hardness), BIRD — поле difficulty.
2. Эталонный SQL переводится из диалекта SQLite в PostgreSQL (sqlglot).
3. Вопрос попадает в набор, только если эталон даёт ОДИНАКОВЫЙ результат в исходной
   SQLite и в PostgreSQL: так проверяются сразу и перенос базы, и перевод SQL.
4. Стратифицированная выборка с фиксированным seed: поровну на каждый уровень сложности.

    cd backend && uv run python -m evals.build_benchmarks spider --per-level 50
    cd backend && uv run python -m evals.build_benchmarks bird --per-level 50
"""

import argparse
import asyncio
import functools
import json
import random
import sqlite3
from collections import Counter, defaultdict
from typing import Any

import asyncpg
from dotenv import load_dotenv
from sqlglot import exp, parse_one

from evals.benchdb import SIMPLE, database_name, sqlite_path
from evals.hardness import hardness
from evals.metrics import has_order_by, results_equal
from evals.paths import BIRD, DATASETS, ROOT, SPIDER, target_url

SEED = 2026
LEVELS = {
    "spider": ["easy", "medium", "hard", "extra"],
    "bird": ["simple", "moderate", "challenging"],
}
# BIRD: три самые большие базы (0,25–0,57 ГБ) не используются — см. EVALS.md
BIRD_DBS = [
    "california_schools",
    "debit_card_specializing",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]
GOLD_TIMEOUT = "30s"


def to_postgres(sql: str, names: set[str] | None = None) -> str:
    """SQLite → PostgreSQL: простые имена в кавычках → без кавычек и в нижнем регистре
    (так таблицы созданы в evals.benchdb), REAL → DOUBLE PRECISION (в SQLite REAL 8-байтный).

    names — имена таблиц и столбцов базы (нижний регистр). SQLite читает "English" как
    строку, если такого столбца нет, — в Spider так записана часть литералов.
    """
    tree = parse_one(sql, dialect="sqlite")
    if names is not None:
        for column in list(tree.find_all(exp.Column)):
            ident = column.this
            if (
                isinstance(ident, exp.Identifier)
                and ident.quoted
                and not column.table
                and ident.name.lower() not in names
            ):
                column.replace(exp.Literal.string(ident.name))
    for ident in tree.find_all(exp.Identifier):
        if SIMPLE.fullmatch(ident.name):
            ident.set("this", ident.name.lower())
            ident.set("quoted", False)
    for dtype in tree.find_all(exp.DataType):
        if dtype.this in (exp.DataType.Type.FLOAT, exp.DataType.Type.DOUBLE):
            dtype.set("this", exp.DataType.Type.DOUBLE)
    return tree.sql(dialect="postgres")


def load_candidates(bench: str) -> list[dict[str, Any]]:
    if bench == "spider":
        raw = json.loads((SPIDER / "dev.json").read_text(encoding="utf-8"))
        return [
            {
                "db_id": r["db_id"],
                "question": r["question"],
                "gold_sql_sqlite": r["query"],
                "difficulty": hardness(r["sql"]),
                "source_index": i,
            }
            for i, r in enumerate(raw)
        ]
    raw = json.loads((BIRD / "dev.json").read_text(encoding="utf-8"))
    return [
        {
            "db_id": r["db_id"],
            "question": r["question"],
            "evidence": r.get("evidence", ""),
            "gold_sql_sqlite": r["SQL"],
            "difficulty": r["difficulty"],
            "source_index": r["question_id"],
        }
        for r in raw
        if r["db_id"] in BIRD_DBS
    ]


@functools.cache
def schema_names(bench: str, db_id: str) -> set[str]:
    con = sqlite3.connect(f"file:{sqlite_path(bench, db_id)}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        names = {t.lower() for t in tables}
        for t in tables:
            names |= {c[1].lower() for c in con.execute(f'PRAGMA table_info("{t}")')}
        return names
    finally:
        con.close()


def run_sqlite(bench: str, db_id: str, sql: str) -> list[tuple[Any, ...]]:
    con = sqlite3.connect(f"file:{sqlite_path(bench, db_id)}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


async def verify(bench: str, case: dict[str, Any], pools: dict[str, asyncpg.Pool]) -> str | None:
    """Причина отбраковки или None, если эталон одинаков в SQLite и PostgreSQL."""
    try:
        expected = run_sqlite(bench, case["db_id"], case["gold_sql_sqlite"])
    except sqlite3.Error as e:
        return f"sqlite: {e}"
    try:
        pg_sql = to_postgres(case["gold_sql_sqlite"], schema_names(bench, case["db_id"]))
    except Exception as e:
        return f"transpile: {type(e).__name__}"
    pool = pools[case["db_id"]]
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(pg_sql)
    except (TimeoutError, asyncpg.PostgresError) as e:
        return f"postgres: {type(e).__name__}"
    actual = [tuple(r.values()) for r in rows]
    if not results_equal(expected, actual, has_order_by(pg_sql)):
        return "results differ"
    case["gold_sql"] = pg_sql
    case["gold_rows"] = len(actual)
    return None


async def build(bench: str, per_level: int) -> None:
    candidates = load_candidates(bench)
    random.Random(SEED).shuffle(candidates)
    db_ids = sorted({c["db_id"] for c in candidates})
    pools = {
        db: await asyncpg.create_pool(
            target_url(database_name(bench, db)),
            min_size=0,
            max_size=2,
            server_settings={"statement_timeout": GOLD_TIMEOUT},
        )
        for db in db_ids
    }
    picked: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected: Counter[str] = Counter()
    try:
        for case in candidates:
            level = case["difficulty"]
            if len(picked[level]) >= per_level:
                continue
            reason = await verify(bench, case, pools)
            if reason is None:
                picked[level].append(case)
            else:
                rejected[reason.split(":")[0]] += 1
            if all(len(picked[lv]) >= per_level for lv in LEVELS[bench]):
                break
    finally:
        for pool in pools.values():
            await pool.close()

    out_dir = DATASETS / f"{bench}_subset"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for level in LEVELS[bench]:
        for i, case in enumerate(sorted(picked[level], key=lambda c: c["source_index"])):
            rows.append({"id": f"{bench}-{level}-{i + 1:03d}", **case})
    (out_dir / f"{bench}_subset.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "bench": bench,
                "picked": {lv: len(picked[lv]) for lv in LEVELS[bench]},
                "rejected": dict(rejected),
                "databases": sorted({r["db_id"] for r in rows}),
            },
            ensure_ascii=False,
        )
    )


async def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bench", choices=["spider", "bird"])
    parser.add_argument("--per-level", type=int, default=50)
    args = parser.parse_args()
    await build(args.bench, args.per_level)


if __name__ == "__main__":
    asyncio.run(main())
