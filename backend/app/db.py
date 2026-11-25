import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, row_factory=dict_row)
