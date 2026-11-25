from collections.abc import Iterator

import psycopg

from app.db import connect


def get_conn() -> Iterator[psycopg.Connection]:
    with connect() as conn:
        yield conn
