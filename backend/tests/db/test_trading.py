from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest

from tests.factories import (buy, make_asset, make_fill, make_order, make_period, make_portfolio,
                             make_session, make_user, sell, set_limit)

T0 = datetime(2019, 1, 2, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def setup(db):
    user = make_user(db)
    session = make_session(db, user, T0)
    portfolio = make_portfolio(db, session, user)
    asset = make_asset(db)
    return {"user": user, "session": session, "portfolio": portfolio, "asset": asset}


def cash(db, portfolio_id) -> Decimal:
    return db.execute("SELECT cash FROM portfolio WHERE id = %s", (portfolio_id,)).fetchone()["cash"]


def test_portfolio_starts_with_initial_cash(db, setup):
    assert cash(db, setup["portfolio"]) == Decimal("10000.00")


def test_buy_fill_reduces_cash(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100.00", T0, fee=1)
    assert cash(db, setup["portfolio"]) == Decimal("8999.00")


def test_sell_fill_increases_cash(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100.00", T0)
    sell(db, setup["portfolio"], setup["asset"], 4, "110.00", T0, fee=1)
    assert cash(db, setup["portfolio"]) == Decimal("9439.00")


def test_fill_marks_order_filled(db, setup):
    order = buy(db, setup["portfolio"], setup["asset"], 1, "10", T0)
    assert db.execute("SELECT status FROM trade_order WHERE id = %s", (order,)).fetchone()["status"] == "filled"


def test_buy_beyond_cash_rejected(db, setup):
    with pytest.raises(psycopg.errors.CheckViolation):
        buy(db, setup["portfolio"], setup["asset"], 101, "100.00", T0)


def test_sell_more_than_held_rejected(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 5, "100", T0)
    with pytest.raises(psycopg.errors.RaiseException, match="insufficient_position"):
        sell(db, setup["portfolio"], setup["asset"], 6, "100", T0)


def test_fill_quantity_must_match_order(db, setup):
    order = make_order(db, setup["portfolio"], setup["asset"], "buy", 5, T0)
    with pytest.raises(psycopg.errors.RaiseException, match="fill_quantity_mismatch"):
        make_fill(db, order, "10", 4, T0)


def test_position_view_avg_cost(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100", T0)
    buy(db, setup["portfolio"], setup["asset"], 10, "110", T0)
    row = db.execute("SELECT net_qty, avg_cost FROM position WHERE portfolio_id = %s",
                     (setup["portfolio"],)).fetchone()
    assert row["net_qty"] == Decimal("20")
    assert row["avg_cost"] == Decimal("105")


def test_closed_position_not_listed(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    sell(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    assert db.execute("SELECT * FROM position WHERE portfolio_id = %s", (setup["portfolio"],)).fetchall() == []


def test_fill_is_immutable(db, setup):
    order = make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)
    fill = make_fill(db, order, "10", 1, T0)
    with pytest.raises(psycopg.errors.RaiseException, match="fill_is_immutable"):
        db.execute("UPDATE fill SET price = 1 WHERE id = %s", (fill,))


def _two_periods(db, setup):
    p1 = make_period(db, setup["session"], 1, T0, T0 + timedelta(days=15))
    p2 = make_period(db, setup["session"], 2, T0 + timedelta(days=15), T0 + timedelta(days=30))
    return p1, p2


def test_max_orders_per_period(db, setup):
    p1, _ = _two_periods(db, setup)
    set_limit(db, setup["portfolio"], p1, max_orders=2)
    make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)
    make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0 + timedelta(days=1))
    with pytest.raises(psycopg.errors.RaiseException, match="period_limit_exceeded"):
        make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0 + timedelta(days=2))


def test_max_buy_amount_per_period(db, setup):
    p1, _ = _two_periods(db, setup)
    set_limit(db, setup["portfolio"], p1, max_buy_amount=1000)
    buy(db, setup["portfolio"], setup["asset"], 6, "100", T0)
    with pytest.raises(psycopg.errors.RaiseException, match="period_limit_exceeded"):
        buy(db, setup["portfolio"], setup["asset"], 6, "100", T0 + timedelta(days=1))


def test_max_sell_amount_per_period(db, setup):
    p1, _ = _two_periods(db, setup)
    set_limit(db, setup["portfolio"], p1, max_sell_amount=500)
    buy(db, setup["portfolio"], setup["asset"], 10, "100", T0)
    with pytest.raises(psycopg.errors.RaiseException, match="period_limit_exceeded"):
        sell(db, setup["portfolio"], setup["asset"], 6, "100", T0 + timedelta(days=1))


def test_limits_reset_next_period(db, setup):
    p1, p2 = _two_periods(db, setup)
    set_limit(db, setup["portfolio"], p1, max_buy_amount=1000)
    set_limit(db, setup["portfolio"], p2, max_buy_amount=1000)
    buy(db, setup["portfolio"], setup["asset"], 6, "100", T0)
    buy(db, setup["portfolio"], setup["asset"], 6, "100", T0 + timedelta(days=16))


def test_fill_crossing_period_counts_against_order_period(db, setup):
    p1, p2 = _two_periods(db, setup)
    set_limit(db, setup["portfolio"], p1, max_buy_amount=1000)
    set_limit(db, setup["portfolio"], p2, max_buy_amount=100000)
    buy(db, setup["portfolio"], setup["asset"], 6, "100", T0)
    last_moment_of_p1 = T0 + timedelta(days=15) - timedelta(seconds=1)
    order = make_order(db, setup["portfolio"], setup["asset"], "buy", 6, last_moment_of_p1)
    with pytest.raises(psycopg.errors.RaiseException, match="period_limit_exceeded"):
        make_fill(db, order, "100", 6, T0 + timedelta(days=16))


def test_replay_sim_time_outside_range_rejected(db):
    user = make_user(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        make_session(db, user, T0, end=T0 + timedelta(days=10), sim_time=T0 + timedelta(days=11))


def test_tiny_buy_rounds_cost_up(db, setup):
    buy(db, setup["portfolio"], setup["asset"], "0.0001", "1", T0)
    assert cash(db, setup["portfolio"]) == Decimal("9999.99")


def test_tiny_sell_rounds_proceeds_down(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 1, "1", T0)
    sell(db, setup["portfolio"], setup["asset"], "0.0001", "1", T0)
    assert cash(db, setup["portfolio"]) == Decimal("9999.00")


def test_order_must_be_placed_at_session_clock(db, setup):
    with pytest.raises(psycopg.errors.RaiseException, match="order_time_mismatch"):
        db.execute(
            "INSERT INTO trade_order (portfolio_id, asset_id, side, quantity, placed_at_sim) "
            "VALUES (%s, %s, 'buy', 1, %s)",
            (setup["portfolio"], setup["asset"], T0 - timedelta(days=1)),
        )


def test_order_outside_any_period_rejected_when_periods_exist(db, setup):
    _two_periods(db, setup)
    with pytest.raises(psycopg.errors.RaiseException, match="no_trading_period"):
        make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0 + timedelta(days=40))


def test_fill_cannot_be_after_session_clock(db, setup):
    order = make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)
    with pytest.raises(psycopg.errors.RaiseException, match="fill_time_invalid"):
        db.execute(
            "INSERT INTO fill (order_id, filled_at_sim, price, quantity) VALUES (%s, %s, 10, 1)",
            (order, T0 + timedelta(days=1)),
        )


def test_fill_cannot_precede_order(db, setup):
    order = make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0 + timedelta(days=1))
    with pytest.raises(psycopg.errors.RaiseException, match="fill_time_invalid"):
        db.execute(
            "INSERT INTO fill (order_id, filled_at_sim, price, quantity) VALUES (%s, %s, 10, 1)",
            (order, T0),
        )
