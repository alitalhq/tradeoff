"""Small insert helpers shared by database tests."""

from datetime import datetime, timedelta
from decimal import Decimal

_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


def make_user(db, email: str | None = None) -> int:
    email = email or f"user{_next()}@example.com"
    return db.execute(
        "INSERT INTO app_user (email, password_hash, display_name) VALUES (%s, 'x', 'Trader') RETURNING id",
        (email,),
    ).fetchone()["id"]


def make_asset(db, symbol: str | None = None) -> int:
    symbol = symbol or f"T{_next()}"
    sector = db.execute(
        "INSERT INTO sector (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
        ("Technology",),
    ).fetchone()["id"]
    exchange = db.execute("SELECT id FROM exchange WHERE code = 'NASDAQ'").fetchone()["id"]
    return db.execute(
        "INSERT INTO asset (symbol, name, sector_id, exchange_id) VALUES (%s, %s, %s, %s) RETURNING id",
        (symbol, symbol + " Inc", sector, exchange),
    ).fetchone()["id"]


def make_bar(db, asset_id: int, start: datetime, open_, high=None, low=None, close=None,
             timeframe: str = "1d", length: timedelta | None = None, volume: int = 1000) -> None:
    length = length or (timedelta(days=1) if timeframe == "1d" else
                        timedelta(hours=1) if timeframe == "1h" else timedelta(minutes=1))
    open_ = Decimal(str(open_))
    close = Decimal(str(close if close is not None else open_))
    high = Decimal(str(high if high is not None else max(open_, close)))
    low = Decimal(str(low if low is not None else min(open_, close)))
    db.execute(
        "INSERT INTO price_bar (asset_id, timeframe, bar_start, bar_end, open, high, low, close, volume) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (asset_id, timeframe, start, start + length, open_, high, low, close, volume),
    )


def make_news(db, published_at: datetime, asset_ids: list[int], headline: str = "Headline") -> int:
    news_id = db.execute(
        "INSERT INTO news (source, external_id, headline, summary, url, published_at) "
        "VALUES ('test', %s, %s, '', 'https://example.com', %s) RETURNING id",
        (str(_next()), headline, published_at),
    ).fetchone()["id"]
    for asset_id in asset_ids:
        db.execute("INSERT INTO news_asset (news_id, asset_id) VALUES (%s, %s)", (news_id, asset_id))
    return news_id
