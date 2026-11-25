import psycopg
import pytest

from app.migrate import apply_migrations
from tests.conftest import table_exists


def test_apply_migrations_is_idempotent(tmp_db_conn, tmp_path):
    (tmp_path / "001_a.sql").write_text("CREATE TABLE a(id int);")
    (tmp_path / "002_b.sql").write_text("CREATE TABLE b(id int);")
    assert apply_migrations(tmp_db_conn, tmp_path) == ["001_a.sql", "002_b.sql"]
    assert apply_migrations(tmp_db_conn, tmp_path) == []


def test_failed_migration_rolls_back(tmp_db_conn, tmp_path):
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE x(id int); SELEC 1;")
    with pytest.raises(psycopg.errors.SyntaxError):
        apply_migrations(tmp_db_conn, tmp_path)
    assert not table_exists(tmp_db_conn, "x")
