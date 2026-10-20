"""Загрузка баз Spider и BIRD (SQLite) в PostgreSQL контейнера target-db.

Каждая база — отдельная БД `spider_<db_id>` / `bird_<db_id>` с правами роли только
для чтения, как у демо-БД (demo_db/roles.sql). Типы столбцов выводятся по данным:
SQLite типизирован динамически, и объявленный INTEGER может содержать текст.

Имена: простые идентификаторы приводятся к нижнему регистру (PostgreSQL сворачивает
регистр так же, поэтому эталонный SQL работает без кавычек), остальные — в кавычках
как есть («Free Meal Count (K-12)» в BIRD).

    cd backend && uv run python -m evals.benchdb spider        # все БД из spider_subset
    cd backend && uv run python -m evals.benchdb bird california_schools financial
"""

import argparse
import asyncio
import csv
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncpg
import structlog
from dotenv import load_dotenv

from evals.paths import BIRD, ROOT, SPIDER, target_url

log = structlog.get_logger()

SIMPLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# зарезервированные слова PostgreSQL, которые встречаются как имена в Spider/BIRD
RESERVED = {"order", "user", "group", "end", "time", "year", "date", "from", "to", "table"}


def pg_name(name: str) -> str:
    """Имя в PostgreSQL: простое — нижним регистром, остальные — как есть."""
    return name.lower() if SIMPLE.fullmatch(name) else name


def quote(name: str) -> str:
    pg = pg_name(name)
    if SIMPLE.fullmatch(pg) and pg not in RESERVED:
        return pg
    return '"' + pg.replace('"', '""') + '"'


def database_name(bench: str, db_id: str) -> str:
    return f"{bench}_{db_id}".lower()


def sqlite_path(bench: str, db_id: str) -> Path:
    if bench == "spider":
        return SPIDER / "database" / db_id / f"{db_id}.sqlite"
    return BIRD / "dev_databases" / db_id / f"{db_id}.sqlite"


@dataclass
class Column:
    name: str
    declared: str
    pk: int
    pg_type: str = "text"
    comment: str | None = None


@dataclass
class Table:
    name: str
    columns: list[Column]
    rows: list[tuple[Any, ...]]
    fks: list[tuple[str, str, str]] = field(default_factory=list)  # (col, ref_table, ref_col)
    comment: str | None = None


def infer_type(declared: str, values: list[Any]) -> str:
    d = declared.upper()
    present = [v for v in values if v is not None]
    if any(isinstance(v, (str, bytes)) for v in present):
        return "text"
    if present and all(isinstance(v, int) for v in present) and "REAL" not in d:
        return "bigint"
    if present and all(isinstance(v, (int, float)) for v in present):
        return "double precision"
    # пустой столбец — тип по объявлению
    if "INT" in d:
        return "bigint"
    if any(t in d for t in ("REAL", "FLOA", "DOUB", "NUMERIC", "DECIMAL")):
        return "double precision"
    return "text"


def convert(value: Any, pg_type: str) -> Any:
    if value is None:
        return None
    if pg_type == "text":
        return value.hex() if isinstance(value, bytes) else str(value)
    if pg_type == "bigint":
        return int(value)
    return float(value)


def read_bird_descriptions(db_dir: Path) -> dict[str, dict[str, str]]:
    """BIRD: описания столбцов из database_description/<table>.csv → комментарии."""
    out: dict[str, dict[str, str]] = {}
    desc = db_dir / "database_description"
    for path in sorted(desc.glob("*.csv")) if desc.exists() else []:
        raw = path.read_bytes()
        text = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        assert text is not None
        cols: dict[str, str] = {}
        for row in csv.DictReader(text.splitlines()):
            name = (row.get("original_column_name") or "").strip()
            parts = [
                (row.get("column_description") or "").strip(),
                (row.get("value_description") or "").strip(),
            ]
            description = ". ".join(p for p in parts if p).replace("\n", " ")
            if name and description:
                cols[name.lower()] = description[:500]
        out[path.stem.lower()] = cols
    return out


def read_sqlite(path: Path, descriptions: dict[str, dict[str, str]]) -> list[Table]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        names = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        tables = []
        for name in names:
            info = con.execute(f'PRAGMA table_info("{name}")').fetchall()
            rows = con.execute(f'SELECT * FROM "{name}"').fetchall()
            columns = [Column(name=c[1], declared=c[2] or "", pk=c[5]) for c in info]
            for i, col in enumerate(columns):
                col.pg_type = infer_type(col.declared, [r[i] for r in rows])
                col.comment = descriptions.get(name.lower(), {}).get(col.name.lower())
            fks = [
                (fk[3], fk[2], fk[4] or "")
                for fk in con.execute(f'PRAGMA foreign_key_list("{name}")').fetchall()
            ]
            tables.append(Table(name=name, columns=columns, rows=rows, fks=fks))
        align_fk_types(tables)
        return tables
    finally:
        con.close()


def convertible(values: list[Any], pg_type: str) -> bool:
    try:
        for v in values:
            convert(v, pg_type)
    except (TypeError, ValueError):
        return False
    return True


def align_fk_types(tables: list[Table]) -> None:
    """FK и целевой столбец должны совпадать по типу, иначе PostgreSQL не создаст связь.

    В Spider ключ бывает объявлен INT в одной таблице и TEXT в другой: если значения
    приводятся к типу целевого столбца — приводим, иначе оба столбца становятся text.
    """
    by_name = {t.name.lower(): t for t in tables}
    for t in tables:
        for col_name, ref_table, ref_col in t.fks:
            ref = by_name.get(ref_table.lower())
            if ref is None:
                continue
            target_name = ref_col or next((c.name for c in ref.columns if c.pk), "")
            idx = next(
                (i for i, c in enumerate(t.columns) if c.name.lower() == col_name.lower()), None
            )
            ref_idx = next(
                (i for i, c in enumerate(ref.columns) if c.name.lower() == target_name.lower()),
                None,
            )
            if idx is None or ref_idx is None:
                continue
            col, target = t.columns[idx], ref.columns[ref_idx]
            if col.pg_type == target.pg_type:
                continue
            if convertible([r[idx] for r in t.rows], target.pg_type):
                col.pg_type = target.pg_type
            else:
                col.pg_type = target.pg_type = "text"


async def create_database(admin: asyncpg.Connection, dbname: str) -> None:
    await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{dbname}"')


async def load_tables(conn: asyncpg.Connection, tables: list[Table]) -> dict[str, int]:
    counts: dict[str, int] = {}
    by_name = {t.name.lower(): t for t in tables}
    for t in tables:
        cols = ", ".join(f"{quote(c.name)} {c.pg_type}" for c in t.columns)
        await conn.execute(f"CREATE TABLE {quote(t.name)} ({cols})")
        records = [
            tuple(convert(v, c.pg_type) for v, c in zip(row, t.columns, strict=True))
            for row in t.rows
        ]
        await conn.copy_records_to_table(
            pg_name(t.name), records=records, columns=[pg_name(c.name) for c in t.columns]
        )
        counts[t.name] = len(records)
        for c in t.columns:
            if c.comment:
                await conn.execute(
                    f"COMMENT ON COLUMN {quote(t.name)}.{quote(c.name)} IS $${c.comment}$$"
                )

    # PK — если данные уникальны; FK — NOT VALID (в Spider ссылки бывают битыми)
    for t in tables:
        pk = [c for c in sorted(t.columns, key=lambda c: c.pk) if c.pk]
        if pk:
            try:
                await conn.execute(
                    f"ALTER TABLE {quote(t.name)} ADD PRIMARY KEY "
                    f"({', '.join(quote(c.name) for c in pk)})"
                )
            except asyncpg.PostgresError as e:
                log.warning("pk_skipped", table=t.name, reason=str(e)[:80])
    for t in tables:
        for col, ref_table, ref_col in t.fks:
            ref = by_name.get(ref_table.lower())
            if ref is None:
                continue
            target = ref_col or next((c.name for c in ref.columns if c.pk), "")
            if not target:
                continue
            try:
                await conn.execute(
                    f"ALTER TABLE {quote(t.name)} ADD FOREIGN KEY ({quote(col)}) "
                    f"REFERENCES {quote(ref.name)} ({quote(target)}) NOT VALID"
                )
            except asyncpg.PostgresError as e:
                log.warning("fk_skipped", table=t.name, column=col, reason=str(e)[:80])
    await conn.execute("ANALYZE")
    return counts


async def grant_reader(conn: asyncpg.Connection, dbname: str, reader: str) -> None:
    """Права как у демо-БД (demo_db/roles.sql): CONNECT, USAGE, SELECT — и ничего больше."""
    await conn.execute(f'REVOKE ALL ON DATABASE "{dbname}" FROM PUBLIC')
    await conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
    await conn.execute(f'GRANT CONNECT ON DATABASE "{dbname}" TO "{reader}"')
    await conn.execute(f'GRANT USAGE ON SCHEMA public TO "{reader}"')
    await conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{reader}"')


async def load(bench: str, db_id: str) -> dict[str, int]:
    import os

    path = sqlite_path(bench, db_id)
    descriptions = read_bird_descriptions(path.parent) if bench == "bird" else {}
    tables = read_sqlite(path, descriptions)
    dbname = database_name(bench, db_id)
    admin = await asyncpg.connect(target_url("postgres", admin=True))
    try:
        await create_database(admin, dbname)
    finally:
        await admin.close()
    conn = await asyncpg.connect(target_url(dbname, admin=True))
    try:
        counts = await load_tables(conn, tables)
        await grant_reader(conn, dbname, os.environ["TARGET_DB_READER_USER"])
    finally:
        await conn.close()
    log.info("benchmark_db_loaded", database=dbname, tables=len(counts), rows=sum(counts.values()))
    return counts


def subset_db_ids(bench: str) -> list[str]:
    import json

    path = ROOT / "evals" / "datasets" / f"{bench}_subset" / f"{bench}_subset.jsonl"
    return sorted({json.loads(line)["db_id"] for line in path.read_text().splitlines() if line})


async def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bench", choices=["spider", "bird"])
    parser.add_argument("db_ids", nargs="*", help="по умолчанию — все БД из <bench>_subset")
    args = parser.parse_args()
    for db_id in args.db_ids or subset_db_ids(args.bench):
        await load(args.bench, db_id)


if __name__ == "__main__":
    asyncio.run(main())
