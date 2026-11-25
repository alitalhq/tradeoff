import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://tradeoff:tradeoff@localhost:55432/tradeoff_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("APP_ENV", "test")

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def _admin_url(url: str) -> str:
    return url.rsplit("/", 1)[0] + "/postgres"


def _recreate_database(url: str) -> None:
    name = url.rsplit("/", 1)[1]
    with psycopg.connect(_admin_url(url), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{name}"')


def table_exists(conn: psycopg.Connection, name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) AS t", (name,)).fetchone()
    value = row["t"] if isinstance(row, dict) else row[0]
    return value is not None


@pytest.fixture(scope="session")
def db_dsn() -> str:
    from app.migrate import apply_migrations

    _recreate_database(TEST_DATABASE_URL)
    with psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row) as conn:
        apply_migrations(conn, MIGRATIONS_DIR)
    return TEST_DATABASE_URL


@pytest.fixture
def db(db_dsn):
    with psycopg.connect(db_dsn, row_factory=dict_row) as conn:
        conn.autocommit = False
        try:
            yield conn
        finally:
            conn.rollback()


@pytest.fixture
def tmp_db_conn():
    url = TEST_DATABASE_URL + "_tmp"
    _recreate_database(url)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn


@pytest.fixture
def client(db_dsn):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
