"""Роль агента s2d_reader может только читать (уровень 5 валидатора, defense in depth).

Каждая опасная команда проверяется дважды:
- в обычной сессии (действует default_transaction_read_only = on);
- после явного переключения сессии в режим записи — так проверяются именно права,
  потому что read-only режим пользователь может отключить сам.
"""

import time

import psycopg
import pytest
from psycopg import errors

FORBIDDEN = {
    "insert": "INSERT INTO regions (id, name, region_type) VALUES (99, 'X', 'city')",
    "update": "UPDATE orders SET total_amount = 0",
    "delete": "DELETE FROM payments",
    "truncate": "TRUNCATE returns",
    "drop_table": "DROP TABLE orders",
    "alter_table": "ALTER TABLE orders ADD COLUMN hacked int",
    "create_table": "CREATE TABLE hacked (id int)",
    "create_temp_table": "CREATE TEMP TABLE hacked (id int)",
    "create_function": "CREATE FUNCTION hacked() RETURNS int AS 'SELECT 1' LANGUAGE sql",
    "create_index": "CREATE INDEX hacked_idx ON orders (status)",
    "select_into": "SELECT * INTO hacked FROM regions",
    "select_for_update": "SELECT * FROM orders WHERE id = 1 FOR UPDATE",
    "copy_to_file": "COPY orders TO '/tmp/orders.csv'",
    "read_server_file": "SELECT pg_read_file('/etc/passwd')",
    "list_server_dir": "SELECT pg_ls_dir('.')",
    "create_role": "CREATE ROLE hacker",
    "data_modifying_cte": "WITH d AS (DELETE FROM returns RETURNING *) SELECT count(*) FROM d",
}

DENIED = (
    errors.InsufficientPrivilege,
    errors.ReadOnlySqlTransaction,
)


@pytest.mark.parametrize("statement", FORBIDDEN.values(), ids=FORBIDDEN.keys())
def test_forbidden_in_default_session(reader: psycopg.Connection, statement: str) -> None:
    with pytest.raises(DENIED):
        reader.execute(statement)


@pytest.mark.parametrize("statement", FORBIDDEN.values(), ids=FORBIDDEN.keys())
def test_forbidden_even_after_disabling_read_only(
    reader: psycopg.Connection, statement: str
) -> None:
    reader.execute("SET TRANSACTION READ WRITE")
    with pytest.raises(errors.InsufficientPrivilege):
        reader.execute(statement)


def test_grant_has_no_effect(reader: psycopg.Connection, admin: psycopg.Connection) -> None:
    """Без права на выдачу GRANT не падает, а выдаёт WARNING и ничего не меняет."""
    reader.execute("SET TRANSACTION READ WRITE")
    reader.execute("GRANT SELECT ON orders TO PUBLIC")
    reader.commit()
    row = admin.execute("SELECT has_table_privilege('public', 'orders', 'SELECT')").fetchone()
    assert row == (False,)


def test_select_is_allowed(reader: psycopg.Connection) -> None:
    row = reader.execute(
        "SELECT count(*) FROM orders o JOIN customers c ON c.id = o.customer_id"
    ).fetchone()
    assert row is not None and row[0] > 0


def test_session_settings(reader: psycopg.Connection) -> None:
    def show(name: str) -> str:
        row = reader.execute(f"SHOW {name}").fetchone()
        assert row is not None
        return str(row[0])

    assert show("default_transaction_read_only") == "on"
    assert show("statement_timeout") == "5s"
    assert show("timezone") == "Asia/Almaty"


def test_long_query_is_cancelled_by_timeout(reader: psycopg.Connection) -> None:
    started = time.monotonic()
    with pytest.raises(errors.QueryCanceled):
        reader.execute("SELECT pg_sleep(10)")
    assert time.monotonic() - started < 7


def test_reader_is_not_privileged(admin: psycopg.Connection) -> None:
    row = admin.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
        "FROM pg_roles WHERE rolname = 's2d_reader'"
    ).fetchone()
    assert row == (False, False, False, False)


def test_public_has_no_database_privileges(admin: psycopg.Connection) -> None:
    row = admin.execute(
        "SELECT has_database_privilege('public', current_database(), 'CONNECT'), "
        "       has_database_privilege('public', current_database(), 'TEMP'), "
        "       has_schema_privilege('public', 'public', 'CREATE')"
    ).fetchone()
    assert row == (False, False, False)
