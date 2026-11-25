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


def make_session(db, user_id: int, start: datetime, end: datetime | None = None,
                 sim_time: datetime | None = None, mode: str = "replay", initial_cash=10000,
                 bar_timeframe: str = "1d", period_length_days: int | None = None) -> int:
    end = end if end is not None else (start + timedelta(days=365) if mode == "replay" else None)
    return db.execute(
        "INSERT INTO sim_session (owner_user_id, mode, bar_timeframe, start_at, end_at, sim_time, "
        "status, initial_cash, period_length_days) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'running', %s, %s) RETURNING id",
        (user_id, mode, bar_timeframe, start, end, sim_time or start, Decimal(str(initial_cash)),
         period_length_days),
    ).fetchone()["id"]


def make_period(db, session_id: int, period_no: int, starts_at: datetime, ends_at: datetime) -> int:
    return db.execute(
        "INSERT INTO trading_period (session_id, period_no, starts_at, ends_at) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (session_id, period_no, starts_at, ends_at),
    ).fetchone()["id"]


def make_portfolio(db, session_id: int, user_id: int | None) -> int:
    return db.execute(
        "INSERT INTO portfolio (session_id, user_id) VALUES (%s, %s) RETURNING id",
        (session_id, user_id),
    ).fetchone()["id"]


def set_limit(db, portfolio_id: int, period_id: int, max_buy_amount=None, max_sell_amount=None,
              max_orders: int | None = None) -> None:
    db.execute(
        "INSERT INTO period_limit (portfolio_id, period_id, max_buy_amount, max_sell_amount, max_orders) "
        "VALUES (%s, %s, %s, %s, %s)",
        (portfolio_id, period_id,
         None if max_buy_amount is None else Decimal(str(max_buy_amount)),
         None if max_sell_amount is None else Decimal(str(max_sell_amount)),
         max_orders),
    )


def make_order(db, portfolio_id: int, asset_id: int, side: str, quantity, placed_at: datetime,
               order_type: str = "market", limit_price=None) -> int:
    return db.execute(
        "INSERT INTO trade_order (portfolio_id, asset_id, side, order_type, quantity, limit_price, placed_at_sim) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (portfolio_id, asset_id, side, order_type, Decimal(str(quantity)),
         None if limit_price is None else Decimal(str(limit_price)), placed_at),
    ).fetchone()["id"]


def make_fill(db, order_id: int, price, quantity, filled_at: datetime, fee=0) -> int:
    return db.execute(
        "INSERT INTO fill (order_id, filled_at_sim, price, quantity, fee) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (order_id, filled_at, Decimal(str(price)), Decimal(str(quantity)), Decimal(str(fee))),
    ).fetchone()["id"]


def buy(db, portfolio_id: int, asset_id: int, quantity, price, at: datetime, fee=0) -> int:
    order = make_order(db, portfolio_id, asset_id, "buy", quantity, at)
    make_fill(db, order, price, quantity, at, fee)
    return order


def sell(db, portfolio_id: int, asset_id: int, quantity, price, at: datetime, fee=0) -> int:
    order = make_order(db, portfolio_id, asset_id, "sell", quantity, at)
    make_fill(db, order, price, quantity, at, fee)
    return order


def make_model(db, provider: str = "Anthropic", code: str | None = None, cutoff: str = "2025-01-01") -> int:
    provider_id = db.execute("SELECT id FROM llm_provider WHERE name = %s", (provider,)).fetchone()["id"]
    return db.execute(
        "INSERT INTO llm_model (provider_id, model_code, knowledge_cutoff) VALUES (%s, %s, %s) RETURNING id",
        (provider_id, code or f"model-{_next()}", cutoff),
    ).fetchone()["id"]


def make_credential(db, user_id: int, provider: str = "Anthropic") -> int:
    provider_id = db.execute("SELECT id FROM llm_provider WHERE name = %s", (provider,)).fetchone()["id"]
    return db.execute(
        "INSERT INTO user_api_credential (user_id, provider_id, encrypted_key, key_last4) "
        "VALUES (%s, %s, '\\x00', 'abcd') RETURNING id",
        (user_id, provider_id),
    ).fetchone()["id"]


def make_agent(db, owner_id: int, model_id: int, credential_id: int) -> int:
    return db.execute(
        "INSERT INTO agent (owner_user_id, name, model_id, credential_id, strategy_prompt) "
        "VALUES (%s, %s, %s, %s, 'Buy quality.') RETURNING id",
        (owner_id, f"agent-{_next()}", model_id, credential_id),
    ).fetchone()["id"]


def make_competition(db, creator_id: int, session_id: int, anonymized: bool = True) -> int:
    return db.execute(
        "INSERT INTO competition (created_by, session_id, anonymized, decision_interval) "
        "VALUES (%s, %s, %s, interval '1 day') RETURNING id",
        (creator_id, session_id, anonymized),
    ).fetchone()["id"]


def add_competitor(db, competition_id: int, session_id: int, agent_id: int | None = None,
                   user_id: int | None = None) -> int:
    portfolio = make_portfolio(db, session_id, user_id)
    return db.execute(
        "INSERT INTO competitor (competition_id, portfolio_id, agent_id) VALUES (%s, %s, %s) RETURNING id",
        (competition_id, portfolio, agent_id),
    ).fetchone()["id"]
