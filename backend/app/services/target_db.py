"""Подключение к пользовательским БД: проверка «только чтение», интроспекция схемы, пулы.

Проверка read-only смотрит на **права** роли, а не на default_transaction_read_only:
этот режим сессия может отключить сама (`SET TRANSACTION READ WRITE`), поэтому
он не является гарантией (см. docs/demo_db.md).
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from asyncpg.pool import PoolConnectionProxy

from app.schemas.schema_snapshot import ColumnInfo, SchemaSnapshot, TableInfo

log = structlog.get_logger()

CONNECT_TIMEOUT_S = 5
SAMPLE_VALUES_LIMIT = 20
SAMPLE_MAX_DISTINCT = 50
SERVER_SETTINGS = {"application_name": "suhbat2db"}

# одиночное соединение или соединение из пула
Conn = asyncpg.Connection | PoolConnectionProxy

# Схемы, которые не показываются агенту и не проверяются на права
SYSTEM_SCHEMAS_SQL = """
    n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND n.nspname NOT LIKE 'pg\\_toast%'
    AND n.nspname NOT LIKE 'pg\\_temp%'
"""


def is_postgres_url(url: str) -> bool:
    return url.startswith(("postgresql://", "postgres://"))


async def connect(url: str) -> asyncpg.Connection:
    return await asyncpg.connect(url, timeout=CONNECT_TIMEOUT_S, server_settings=SERVER_SETTINGS)


# --- Проверка «только чтение» ----------------------------------------------------------------

READONLY_CHECK_SQL = f"""
SELECT
    r.rolsuper, r.rolcreaterole, r.rolcreatedb, r.rolbypassrls,
    has_database_privilege(current_database(), 'CREATE') AS db_create,
    has_database_privilege(current_database(), 'TEMP') AS db_temp,
    pg_has_role(current_user, 'pg_write_server_files', 'MEMBER') AS write_files,
    pg_has_role(current_user, 'pg_read_server_files', 'MEMBER') AS read_files,
    pg_has_role(current_user, 'pg_execute_server_program', 'MEMBER') AS exec_program,
    ARRAY(
        SELECT n.nspname FROM pg_namespace n
        WHERE {SYSTEM_SCHEMAS_SQL} AND has_schema_privilege(n.oid, 'CREATE')
        ORDER BY 1 LIMIT 5
    ) AS writable_schemas,
    ARRAY(
        SELECT n.nspname || '.' || c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f') AND {SYSTEM_SCHEMAS_SQL}
          AND (has_table_privilege(c.oid, 'INSERT') OR has_table_privilege(c.oid, 'UPDATE')
               OR has_table_privilege(c.oid, 'DELETE') OR has_table_privilege(c.oid, 'TRUNCATE'))
        ORDER BY 1 LIMIT 5
    ) AS writable_tables
FROM pg_roles r
WHERE r.rolname = current_user
"""

ROLE_FLAGS = {
    "rolsuper": "роль является суперпользователем",
    "rolcreaterole": "роль может создавать роли",
    "rolcreatedb": "роль может создавать базы данных",
    "rolbypassrls": "роль обходит row-level security",
    "db_create": "есть право CREATE на базу данных",
    "db_temp": "есть право создавать временные таблицы",
    "write_files": "роль может писать файлы сервера (pg_write_server_files)",
    "read_files": "роль может читать файлы сервера (pg_read_server_files)",
    "exec_program": "роль может запускать программы на сервере (pg_execute_server_program)",
}


async def readonly_violations(conn: Conn) -> list[str]:
    """Пустой список — роль безопасна для агента."""
    row = await conn.fetchrow(READONLY_CHECK_SQL)
    if row is None:
        return ["не удалось определить права текущей роли"]
    violations = [text for flag, text in ROLE_FLAGS.items() if row[flag]]
    if row["writable_schemas"]:
        violations.append("есть право CREATE в схемах: " + ", ".join(row["writable_schemas"]))
    if row["writable_tables"]:
        violations.append("есть права на запись в таблицы: " + ", ".join(row["writable_tables"]))
    return violations


# --- Интроспекция ------------------------------------------------------------------------

TABLES_SQL = f"""
SELECT c.oid, n.nspname AS schema_name, c.relname AS name,
       obj_description(c.oid, 'pg_class') AS comment,
       greatest(c.reltuples, 0)::bigint AS row_estimate
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f') AND {SYSTEM_SCHEMAS_SQL}
  AND has_table_privilege(c.oid, 'SELECT')
ORDER BY n.nspname, c.relname
"""

COLUMNS_SQL = """
SELECT a.attrelid AS oid, a.attname AS name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       NOT a.attnotnull AS nullable,
       col_description(a.attrelid, a.attnum) AS comment,
       t.typcategory = 'S' AS is_text
FROM pg_attribute a JOIN pg_type t ON t.oid = a.atttypid
WHERE a.attrelid = ANY($1::oid[]) AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attrelid, a.attnum
"""

KEYS_SQL = """
SELECT con.conrelid AS oid, con.contype::text AS kind, a.attname AS column_name,
       fn.nspname || '.' || fc.relname || '.' || fa.attname AS ref
FROM pg_constraint con
CROSS JOIN LATERAL unnest(con.conkey, coalesce(con.confkey, con.conkey)) AS k(attnum, fattnum)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
LEFT JOIN pg_class fc ON fc.oid = con.confrelid
LEFT JOIN pg_namespace fn ON fn.oid = fc.relnamespace
LEFT JOIN pg_attribute fa ON fa.attrelid = con.confrelid AND fa.attnum = k.fattnum
WHERE con.conrelid = ANY($1::oid[]) AND con.contype IN ('p', 'f')
"""

# Оценка числа различных значений из статистики планировщика (без сканирования таблиц).
# n_distinct < 0 означает долю от числа строк: -1 — все значения уникальны.
STATS_SQL = """
SELECT s.schemaname AS schema_name, s.tablename AS table_name, s.attname AS column_name,
       s.n_distinct
FROM pg_stats s
WHERE s.schemaname NOT IN ('pg_catalog', 'information_schema')
"""

SAMPLE_TIMEOUT = "2s"


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def estimated_distinct(n_distinct: float | None, row_estimate: int) -> float | None:
    if n_distinct is None:
        return None
    return n_distinct if n_distinct > 0 else -n_distinct * row_estimate


async def sample_values(conn: Conn, schema: str, table: str, column: str) -> list[str] | None:
    """Все значения категориального столбца (≤ SAMPLE_VALUES_LIMIT) или None.

    Значения из БД — недоверенные данные: в промпт агента они попадают в границах
    <untrusted_data> (роль 5).
    """
    col = quote_ident(column)
    query = (
        f"SELECT DISTINCT {col}::text AS v FROM {quote_ident(schema)}.{quote_ident(table)} "
        f"WHERE {col} IS NOT NULL ORDER BY 1 LIMIT {SAMPLE_VALUES_LIMIT + 1}"
    )
    try:
        async with conn.transaction(readonly=True):
            await conn.execute(f"SET LOCAL statement_timeout = '{SAMPLE_TIMEOUT}'")
            rows = await conn.fetch(query)
    except asyncpg.PostgresError as e:
        log.info("sample_values_skipped", table=f"{schema}.{table}", column=column, error=str(e))
        return None
    values = [r["v"] for r in rows]
    return values if len(values) <= SAMPLE_VALUES_LIMIT else None


async def introspect(conn: Conn, datasource_id: uuid.UUID) -> SchemaSnapshot:
    tables = await conn.fetch(TABLES_SQL)
    oids = [t["oid"] for t in tables]
    columns = await conn.fetch(COLUMNS_SQL, oids)
    keys = await conn.fetch(KEYS_SQL, oids)
    stats = {
        (r["schema_name"], r["table_name"], r["column_name"]): r["n_distinct"]
        for r in await conn.fetch(STATS_SQL)
    }
    timezone = await conn.fetchval("SELECT current_setting('TimeZone')")

    pks = {(k["oid"], k["column_name"]) for k in keys if k["kind"] == "p"}
    fks = {(k["oid"], k["column_name"]): k["ref"] for k in keys if k["kind"] == "f"}
    names = {t["oid"]: (t["schema_name"], t["name"]) for t in tables}
    rows = {t["oid"]: t["row_estimate"] for t in tables}

    # примеры значений нужны только для категориальных текстовых столбцов (value linking)
    samples: dict[tuple[Any, str], list[str] | None] = {}
    for c in columns:
        if not c["is_text"]:
            continue
        schema_name, table_name = names[c["oid"]]
        distinct = estimated_distinct(
            stats.get((schema_name, table_name, c["name"])), rows[c["oid"]]
        )
        small_table = rows[c["oid"]] <= SAMPLE_MAX_DISTINCT
        if (distinct is not None and distinct <= SAMPLE_MAX_DISTINCT) or small_table:
            samples[(c["oid"], c["name"])] = await sample_values(
                conn, schema_name, table_name, c["name"]
            )

    by_table: dict[Any, list[ColumnInfo]] = {oid: [] for oid in oids}
    for c in columns:
        by_table[c["oid"]].append(
            ColumnInfo(
                name=c["name"],
                data_type=c["data_type"],
                nullable=c["nullable"],
                comment=c["comment"],
                is_pk=(c["oid"], c["name"]) in pks,
                fk=fks.get((c["oid"], c["name"])),
                sample_values=samples.get((c["oid"], c["name"])),
            )
        )

    return SchemaSnapshot(
        datasource_id=str(datasource_id),
        timezone=timezone,
        tables=[
            TableInfo(
                schema_name=t["schema_name"],
                name=t["name"],
                comment=t["comment"],
                row_estimate=t["row_estimate"],
                columns=by_table[t["oid"]],
            )
            for t in tables
        ],
        created_at=datetime.now(UTC),
    )


# --- Пулы соединений ---------------------------------------------------------------------


class TargetPools:
    """Пул соединений на каждый источник данных; создаётся при первом обращении."""

    def __init__(self, max_size: int = 5) -> None:
        self._pools: dict[uuid.UUID, asyncpg.Pool] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def get(self, datasource_id: uuid.UUID, url: str) -> asyncpg.Pool:
        async with self._lock:
            pool = self._pools.get(datasource_id)
            if pool is None:
                pool = await asyncpg.create_pool(
                    url,
                    min_size=0,
                    max_size=self._max_size,
                    timeout=CONNECT_TIMEOUT_S,
                    server_settings=SERVER_SETTINGS,
                )
                self._pools[datasource_id] = pool
            return pool

    async def close(self, datasource_id: uuid.UUID) -> None:
        async with self._lock:
            pool = self._pools.pop(datasource_id, None)
        if pool is not None:
            await pool.close()

    async def close_all(self) -> None:
        async with self._lock:
            pools, self._pools = list(self._pools.values()), {}
        await asyncio.gather(*(p.close() for p in pools), return_exceptions=True)


target_pools = TargetPools()
