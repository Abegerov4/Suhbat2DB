import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _conninfo(user_var: str, password_var: str, default_user: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host=os.environ.get("TARGET_DB_HOST", "localhost"),
        port=os.environ.get("TARGET_DB_PORT", "5443"),
        dbname=os.environ.get("TARGET_DB_NAME", "demo"),
        user=os.environ.get(user_var, default_user),
        password=os.environ.get(password_var, ""),
        connect_timeout=3,
    )


@pytest.fixture(scope="session")
def admin_conninfo() -> str:
    return _conninfo("TARGET_DB_ADMIN_USER", "TARGET_DB_ADMIN_PASSWORD", "target_admin")


@pytest.fixture(scope="session")
def reader_conninfo() -> str:
    return _conninfo("TARGET_DB_READER_USER", "TARGET_DB_READER_PASSWORD", "s2d_reader")


@pytest.fixture(scope="session", autouse=True)
def _require_db(admin_conninfo: str) -> None:
    try:
        psycopg.connect(admin_conninfo).close()
    except psycopg.OperationalError as e:
        pytest.skip(f"target-db недоступна ({e}); запустите make up-lite && make seed")


@pytest.fixture
def admin(admin_conninfo: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(admin_conninfo) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def reader(reader_conninfo: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(reader_conninfo) as conn:
        yield conn
        conn.rollback()
