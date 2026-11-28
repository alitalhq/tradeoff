from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.replay.engine import ReplayError, advance
from tests.factories import (add_session_asset, buy, make_asset, make_bar, make_news, make_order, make_period,
                             make_portfolio, make_session, make_split, make_user, set_limit)

MON = datetime(2019, 1, 7, tzinfo=timezone.utc)
DAY = timedelta(days=1)
OPEN = timedelta(hours=14, minutes=30)
SESSION_LEN = timedelta(hours=6, minutes=30)


def bar(db, asset, day, price=100):
    """Daily bar for `day` (a midnight UTC datetime); returns its bar_end."""
    make_bar(db, asset, day + OPEN, price, length=SESSION_LEN)
    return day + OPEN + SESSION_LEN


@pytest.fixture
def s(db):
    user = make_user(db)
    session = make_session(db, user, MON, end=MON + timedelta(days=30))
    portfolio = make_portfolio(db, session, user)
    asset = make_asset(db)
    return {"user": user, "session": session, "portfolio": portfolio, "asset": asset}


def status(db, session_id):
    return db.execute("SELECT status, sim_time FROM sim_session WHERE id = %s", (session_id,)).fetchone()


def types(result):
    return [m.type for m in result.messages]


def test_step_jumps_to_next_bar_end(db, s):
    mon_end = bar(db, s["asset"], MON)
    bar(db, s["asset"], MON + DAY)
    result = advance(db, s["session"])
    assert result.sim_time == mon_end and result.status == "running"
    assert types(result) == ["clock", "bar"]
    assert status(db, s["session"])["sim_time"] == mon_end


def test_weekend_skipped(db, s):
    fri = MON + 4 * DAY
    fri_end = bar(db, s["asset"], fri)
    next_mon_end = bar(db, s["asset"], fri + 3 * DAY)
    db.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (fri_end, s["session"]))
    assert advance(db, s["session"]).sim_time == next_mon_end


def test_finishes_at_end_at(db, s):
    last = MON + 29 * DAY
    last_end = bar(db, s["asset"], last)
    bar(db, s["asset"], MON + 31 * DAY)
    db.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (last_end, s["session"]))
    result = advance(db, s["session"])
    assert result.status == "finished" and result.sim_time == MON + timedelta(days=30)


def test_no_bars_finishes(db, s):
    result = advance(db, s["session"])
    assert result.status == "finished" and result.sim_time == MON + timedelta(days=30)
    with pytest.raises(ReplayError, match="session_finished"):
        advance(db, s["session"])


def test_gate_at_start_running(db, s):
    make_period(db, s["session"], 1, MON, MON + 15 * DAY)
    bar(db, s["asset"], MON)
    result = advance(db, s["session"])
    assert result.status == "awaiting_limits" and result.sim_time == MON
    assert types(result) == ["clock", "period"]
    assert result.messages[1].awaiting_limits is True


def test_gate_at_start_manual(db, s):
    make_period(db, s["session"], 1, MON, MON + 15 * DAY)
    db.execute("UPDATE sim_session SET status = 'created' WHERE id = %s", (s["session"],))
    with pytest.raises(ReplayError, match="limits_required"):
        advance(db, s["session"], manual=True)


def test_limit_set_opens_gate(db, s):
    period = make_period(db, s["session"], 1, MON, MON + 15 * DAY)
    set_limit(db, s["portfolio"], period)
    mon_end = bar(db, s["asset"], MON)
    assert advance(db, s["session"]).sim_time == mon_end


def test_stops_at_period_start(db, s):
    p2_start = MON + 2 * DAY + timedelta(hours=6)
    p1 = make_period(db, s["session"], 1, MON, p2_start)
    make_period(db, s["session"], 2, p2_start, MON + 30 * DAY)
    set_limit(db, s["portfolio"], p1)
    tue_end = bar(db, s["asset"], MON + DAY)
    bar(db, s["asset"], MON + 2 * DAY)
    db.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (tue_end, s["session"]))
    result = advance(db, s["session"])
    assert result.sim_time == p2_start
    assert result.status == "awaiting_limits"
    period = [m for m in result.messages if m.type == "period"][0]
    assert period.period_no == 2 and period.awaiting_limits is True


def test_manual_step_into_period_stays_paused(db, s):
    p1 = make_period(db, s["session"], 1, MON, MON + timedelta(hours=18))
    make_period(db, s["session"], 2, MON + timedelta(hours=18), MON + 30 * DAY)
    set_limit(db, s["portfolio"], p1)
    bar(db, s["asset"], MON)
    db.execute("UPDATE sim_session SET status = 'paused' WHERE id = %s", (s["session"],))
    result = advance(db, s["session"], manual=True)
    assert result.status == "paused"
    with pytest.raises(ReplayError, match="limits_required"):
        advance(db, s["session"], manual=True)


def test_manual_step_from_created_pauses(db, s):
    bar(db, s["asset"], MON)
    db.execute("UPDATE sim_session SET status = 'created' WHERE id = %s", (s["session"],))
    assert advance(db, s["session"], manual=True).status == "paused"


def test_manual_step_rejected_while_running(db, s):
    with pytest.raises(ReplayError, match="invalid_state"):
        advance(db, s["session"], manual=True)


def test_fill_on_tick(db, s):
    make_order(db, s["portfolio"], s["asset"], "buy", 2, MON)
    bar(db, s["asset"], MON, price=50)
    result = advance(db, s["session"])
    fill = [m for m in result.messages if m.type == "fill"][0]
    assert fill.status == "filled" and fill.price == Decimal("50")


def test_split_applied_on_tick(db, s):
    buy(db, s["portfolio"], s["asset"], 10, 100, MON)
    make_split(db, s["asset"], MON + OPEN, 2)
    bar(db, s["asset"], MON)
    result = advance(db, s["session"])
    adj = [m for m in result.messages if m.type == "adjustment"][0]
    assert adj.action_type == "split" and adj.qty_delta == Decimal("10")
    assert adj.portfolio_id == s["portfolio"]


def test_news_streamed_once(db, s):
    make_news(db, MON + timedelta(hours=10), [s["asset"]])
    bar(db, s["asset"], MON)
    bar(db, s["asset"], MON + DAY)
    assert types(advance(db, s["session"])).count("news") == 1
    assert "news" not in types(advance(db, s["session"]))


def test_paused_session_not_advanced_by_runner(db, s):
    bar(db, s["asset"], MON)
    db.execute("UPDATE sim_session SET status = 'paused' WHERE id = %s", (s["session"],))
    result = advance(db, s["session"])
    assert result.status == "paused" and result.messages == [] and result.sim_time == MON


def test_live_session_rejected(db, s):
    live = make_session(db, s["user"], MON, mode="live")
    with pytest.raises(ReplayError, match="not_replay"):
        advance(db, live)


def test_universe_limits_bars(db, s):
    other = make_asset(db)
    add_session_asset(db, s["session"], s["asset"])
    bar(db, other, MON)
    tue_end = bar(db, s["asset"], MON + DAY)
    result = advance(db, s["session"])
    assert result.sim_time == tue_end
    assert [m.asset_id for m in result.messages if m.type == "bar"] == [s["asset"]]
