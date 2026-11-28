from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest

from tests.factories import (add_session_asset, apply_actions, buy, make_asset, make_dividend, make_order,
                             make_portfolio, make_session, make_split, make_user, sell)

T0 = datetime(2019, 1, 2, 21, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)


@pytest.fixture
def setup(db):
    user = make_user(db)
    session = make_session(db, user, T0)
    portfolio = make_portfolio(db, session, user)
    asset = make_asset(db)
    return {"user": user, "session": session, "portfolio": portfolio, "asset": asset}


def position(db, portfolio_id, asset_id):
    return db.execute(
        "SELECT net_qty, avg_cost FROM position WHERE portfolio_id = %s AND asset_id = %s",
        (portfolio_id, asset_id),
    ).fetchone()


def cash(db, portfolio_id) -> Decimal:
    return db.execute("SELECT cash FROM portfolio WHERE id = %s", (portfolio_id,)).fetchone()["cash"]


def test_awaiting_limits_status_exists(db, setup):
    db.execute("UPDATE sim_session SET status = 'awaiting_limits' WHERE id = %s", (setup["session"],))


def test_split_scales_position_and_avg_cost(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100", T0)
    make_split(db, setup["asset"], T1, 2)
    rows = apply_actions(db, setup["session"], T0, T2)
    assert [r["qty_delta"] for r in rows] == [Decimal("10.0000")]
    pos = position(db, setup["portfolio"], setup["asset"])
    assert pos["net_qty"] == Decimal("20") and pos["avg_cost"] == Decimal("50")


def test_split_after_partial_sell(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100", T0)
    sell(db, setup["portfolio"], setup["asset"], 5, "100", T0)
    make_split(db, setup["asset"], T1, 2)
    apply_actions(db, setup["session"], T0, T2)
    pos = position(db, setup["portfolio"], setup["asset"])
    assert pos["net_qty"] == Decimal("10") and pos["avg_cost"] == Decimal("50")


def test_buy_after_split_is_not_scaled(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "100", T0)
    make_split(db, setup["asset"], T1, 2)
    apply_actions(db, setup["session"], T0, T1)
    buy(db, setup["portfolio"], setup["asset"], 20, "50", T2)
    pos = position(db, setup["portfolio"], setup["asset"])
    assert pos["net_qty"] == Decimal("40") and pos["avg_cost"] == Decimal("50")


def test_reverse_split(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 10, "10", T0)
    make_split(db, setup["asset"], T1, "0.5")
    apply_actions(db, setup["session"], T0, T2)
    pos = position(db, setup["portfolio"], setup["asset"])
    assert pos["net_qty"] == Decimal("5") and pos["avg_cost"] == Decimal("20")


def test_dividend_credits_cash_floor(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    before = cash(db, setup["portfolio"])
    make_dividend(db, setup["asset"], T1, "0.3333")
    rows = apply_actions(db, setup["session"], T0, T2)
    assert rows[0]["cash_delta"] == Decimal("0.99")
    assert cash(db, setup["portfolio"]) == before + Decimal("0.99")


def test_apply_is_idempotent(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    before = cash(db, setup["portfolio"])
    make_dividend(db, setup["asset"], T1, "1")
    apply_actions(db, setup["session"], T0, T2)
    assert apply_actions(db, setup["session"], T0, T2) == []
    assert cash(db, setup["portfolio"]) == before + Decimal("3")


def test_action_outside_window_not_applied(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    make_dividend(db, setup["asset"], T2 + timedelta(days=1), "1")
    assert apply_actions(db, setup["session"], T0, T2) == []


def test_adjustment_cannot_be_ahead_of_clock(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    action = make_dividend(db, setup["asset"], T2, "1")
    with pytest.raises(psycopg.errors.RaiseException, match="adjustment_time_invalid"), db.transaction():
        db.execute(
            "INSERT INTO corporate_action_applied (portfolio_id, corporate_action_id, applied_at_sim, "
            "qty_delta, cash_delta) VALUES (%s, %s, %s, 0, 3)",
            (setup["portfolio"], action, T2),
        )


def test_adjustment_immutable(db, setup):
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    make_dividend(db, setup["asset"], T1, "1")
    apply_actions(db, setup["session"], T0, T2)
    for stmt in ("UPDATE corporate_action_applied SET cash_delta = 100", "DELETE FROM corporate_action_applied"):
        with pytest.raises(psycopg.errors.RaiseException, match="adjustment_is_immutable"), db.transaction():
            db.execute(stmt)


def test_non_holder_gets_no_adjustment(db, setup):
    other = make_portfolio(db, setup["session"], make_user(db))
    buy(db, setup["portfolio"], setup["asset"], 3, "100", T0)
    make_dividend(db, setup["asset"], T1, "1")
    rows = apply_actions(db, setup["session"], T0, T2)
    assert [r["portfolio_id"] for r in rows] == [setup["portfolio"]]
    assert other not in [r["portfolio_id"] for r in rows]


def test_agent_portfolio_is_adjusted(db, setup):
    agent_pf = make_portfolio(db, setup["session"], None)
    buy(db, agent_pf, setup["asset"], 2, "100", T0)
    make_dividend(db, setup["asset"], T1, "1")
    rows = apply_actions(db, setup["session"], T0, T2)
    assert [r["portfolio_id"] for r in rows] == [agent_pf]


def test_order_rejected_on_finished_session(db, setup):
    db.execute("UPDATE sim_session SET status = 'finished' WHERE id = %s", (setup["session"],))
    with pytest.raises(psycopg.errors.RaiseException, match="session_finished"), db.transaction():
        make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)


def test_order_outside_universe_rejected(db, setup):
    add_session_asset(db, setup["session"], make_asset(db))
    with pytest.raises(psycopg.errors.RaiseException, match="asset_not_in_session"), db.transaction():
        make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)


def test_order_inside_universe_accepted(db, setup):
    add_session_asset(db, setup["session"], setup["asset"])
    make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)


def test_empty_universe_is_unrestricted(db, setup):
    make_order(db, setup["portfolio"], setup["asset"], "buy", 1, T0)
