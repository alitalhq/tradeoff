"""Apply numbered SQL migration files in order, each exactly once."""

from pathlib import Path

import psycopg

from app.config import get_settings
from app.db import connect

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migration (
    filename   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    with conn.transaction():
        conn.execute(BOOTSTRAP_SQL)
        applied = {r["filename"] if isinstance(r, dict) else r[0]
                   for r in conn.execute("SELECT filename FROM schema_migration").fetchall()}

    newly_applied: list[str] = []
    for path in sorted(Path(migrations_dir).glob("*.sql")):
        if path.name in applied:
            continue
        with conn.transaction():
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migration (filename) VALUES (%s)", (path.name,))
        newly_applied.append(path.name)
    return newly_applied


def default_migrations_dir() -> Path:
    configured = get_settings().migrations_dir
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "db" / "migrations"


if __name__ == "__main__":
    with connect() as conn:
        for name in apply_migrations(conn, default_migrations_dir()):
            print(f"applied {name}")
