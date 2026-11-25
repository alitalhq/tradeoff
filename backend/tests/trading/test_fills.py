import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.rows import dict_row

from app.trading.fills import FillResult, fill_pending_orders
from app.trading.orders import place_order
from tests.factories import make_asset, make_bar, make_portfolio, make_session, make_user

D1 = datetime(2019, 6, 3, 13, 30, tzinfo=timezone.utc)
DAY = timedelta(days=1)


@pytest.fixture
def ctx(db):
    user = make_user(db)
    session = make_session(db, user, D1 - DAY, sim_time=D1 + DAY)  # D1 bar closed
    asset = make_asset(db)
    make_bar(db, asset, D1, open_=100, high=106, low=99, close=105)
    return {"session": session, "portfolio": make_portfolio(db, session, user), "asset": asset}


def advance(db, session_id, to):
    db.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (to, session_id))


def status(db, order_id):
    return db.execute("SELECT status, reject_reason FROM trade_order WHERE id = %s", (order_id,)).fetchone()


def test_market_order_fills_at_next_bar_open(db, ctx):
    order = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=107, high=110, low=104, close=108)
    advance(db, ctx["session"], D1 + 2 * DAY)
    assert fill_pending_orders(db, ctx["session"]) == [
        FillResult(order_id=order, status="filled", price=Decimal("107.0000"), reason=None)
    ]


def test_order_stays_pending_without_next_bar(db, ctx):
    order = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=107)          # exists but not yet closed
    advance(db, ctx["session"], D1 + DAY + timedelta(hours=1))
    assert fill_pending_orders(db, ctx["session"]) == []
    assert status(db, order)["status"] == "pending"


def test_limit_buy_fills_only_when_low_touches(db, ctx):
    order = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"),
                        order_type="limit", limit_price=Decimal("95"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=101, high=103, low=97, close=102)
    make_bar(db, ctx["asset"], D1 + 2 * DAY, open_=99, high=100, low=94, close=96)
    advance(db, ctx["session"], D1 + 3 * DAY)
    [result] = fill_pending_orders(db, ctx["session"])
    assert result.order_id == order and result.price == Decimal("95")


def test_limit_buy_gap_down_fills_at_open(db, ctx):
    place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"),
                order_type="limit", limit_price=Decimal("95"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=90, high=92, low=88, close=91)
    advance(db, ctx["session"], D1 + 2 * DAY)
    [result] = fill_pending_orders(db, ctx["session"])
    assert result.price == Decimal("90.0000")


def test_limit_sell_fills_at_limit_or_better(db, ctx):
    place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=100)
    advance(db, ctx["session"], D1 + 2 * DAY)
    fill_pending_orders(db, ctx["session"])
    place_order(db, ctx["portfolio"], ctx["asset"], "sell", Decimal("1"),
                order_type="limit", limit_price=Decimal("110"))
    make_bar(db, ctx["asset"], D1 + 2 * DAY, open_=104, high=112, low=103, close=111)
    advance(db, ctx["session"], D1 + 3 * DAY)
    [result] = fill_pending_orders(db, ctx["session"])
    assert result.price == Decimal("110")


def test_rejected_fill_does_not_block_others(db, ctx):
    bad = place_order(db, ctx["portfolio"], ctx["asset"], "sell", Decimal("5"))   # nothing held
    good = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=107)
    advance(db, ctx["session"], D1 + 2 * DAY)
    results = {r.order_id: r for r in fill_pending_orders(db, ctx["session"])}
    assert results[bad].status == "rejected" and results[bad].reason == "insufficient_position"
    assert results[good].status == "filled"
    assert status(db, bad) == {"status": "rejected", "reject_reason": "insufficient_position"}


def test_buy_beyond_cash_rejected_as_insufficient_cash(db, ctx):
    order = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1000"))
    make_bar(db, ctx["asset"], D1 + DAY, open_=107)
    advance(db, ctx["session"], D1 + 2 * DAY)
    [result] = fill_pending_orders(db, ctx["session"])
    assert result == FillResult(order_id=order, status="rejected", price=None, reason="insufficient_cash")


def test_concurrent_fills_cannot_overdraw(db_dsn):
    with psycopg.connect(db_dsn, row_factory=dict_row, autocommit=True) as setup:
        user = make_user(setup)
        session = make_session(setup, user, D1 - DAY, sim_time=D1 + DAY)
        portfolio = make_portfolio(setup, session, user)
        asset = make_asset(setup)
        make_bar(setup, asset, D1, open_=100)
        place_order(setup, portfolio, asset, "buy", Decimal("70"))   # 7000 of 10000 cash
        place_order(setup, portfolio, asset, "buy", Decimal("70"))
        make_bar(setup, asset, D1 + DAY, open_=100)
        setup.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (D1 + 2 * DAY, session))

    barrier = threading.Barrier(2)
    results: list[list[FillResult]] = []

    def worker():
        with psycopg.connect(db_dsn, row_factory=dict_row) as conn:
            barrier.wait()
            results.append(fill_pending_orders(conn, session))
            conn.commit()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with psycopg.connect(db_dsn, row_factory=dict_row) as check:
        statuses = sorted(r["status"] for r in check.execute(
            "SELECT status FROM trade_order WHERE portfolio_id = %s", (portfolio,)).fetchall())
        cash = check.execute("SELECT cash FROM portfolio WHERE id = %s", (portfolio,)).fetchone()["cash"]
    assert statuses == ["filled", "rejected"]
    assert cash == Decimal("3000.00")
