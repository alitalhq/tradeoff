from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends

from app.db import connect


def get_conn() -> Iterator[psycopg.Connection]:
    with connect() as conn:
        yield conn


# scope="function" commits before the response is sent; the default "request" scope would
# commit afterwards, so a client could read stale data right after a 201.
Conn = Annotated[psycopg.Connection, Depends(get_conn, scope="function")]
