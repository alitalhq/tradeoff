"""Session-scoped market reads. Only the *_as_of SQL functions are queried here, never raw tables."""

from decimal import Decimal

import psycopg

from app.market.models import Bar, NewsItem


def get_bars(conn: psycopg.Connection, session_id: int, asset_id: int, timeframe: str, limit: int) -> list[Bar]:
    rows = conn.execute(
        "SELECT * FROM bars_as_of(%s, %s, %s, %s)", (session_id, asset_id, timeframe, limit)
    ).fetchall()
    return [Bar.model_validate(r) for r in rows]


def get_news(conn: psycopg.Connection, session_id: int, asset_id: int | None, limit: int) -> list[NewsItem]:
    rows = conn.execute(
        "SELECT * FROM news_as_of(%s, %s, %s)", (session_id, asset_id, limit)
    ).fetchall()
    return [NewsItem.model_validate(r) for r in rows]


def get_latest_price(conn: psycopg.Connection, session_id: int, asset_id: int) -> Decimal | None:
    row = conn.execute("SELECT latest_price_as_of(%s, %s) AS price", (session_id, asset_id)).fetchone()
    return row["price"]
