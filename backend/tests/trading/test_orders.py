from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.trading.errors import OrderRejected
from app.trading.orders import place_order
from tests.factories import make_asset, make_period, make_portfolio, make_session, make_user, set_limit

T0 = datetime(2019, 1, 2, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def ctx(db):
    user = make_user(db)
    session = make_session(db, user, T0)
    return {"session": session, "portfolio": make_portfolio(db, session, user), "asset": make_asset(db)}


def test_place_order_stamps_session_clock(db, ctx):
    order_id = place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("2"))
    row = db.execute("SELECT placed_at_sim, status FROM trade_order WHERE id = %s", (order_id,)).fetchone()
    assert row == {"placed_at_sim": T0, "status": "pending"}


def test_place_order_over_max_orders_raises(db, ctx):
    period = make_period(db, ctx["session"], 1, T0, T0 + timedelta(days=15))
    set_limit(db, ctx["portfolio"], period, max_orders=1)
    place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    with pytest.raises(OrderRejected) as exc:
        place_order(db, ctx["portfolio"], ctx["asset"], "buy", Decimal("1"))
    assert exc.value.reason == "period_limit_exceeded"
    # The caller's transaction is still usable after a rejection.
    assert db.execute("SELECT count(*) AS n FROM trade_order WHERE portfolio_id = %s",
                      (ctx["portfolio"],)).fetchone()["n"] == 1
