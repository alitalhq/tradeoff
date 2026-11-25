import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.market.read import get_bars, get_latest_price, get_news
from tests.factories import make_asset, make_bar, make_news, make_session, make_user

UTC = timezone.utc
DAY1 = datetime(2019, 6, 3, 13, 30, tzinfo=UTC)


@pytest.fixture
def ctx(db):
    user = make_user(db)
    asset = make_asset(db)
    session = make_session(db, user, DAY1 - timedelta(days=10))
    return {"session": session, "asset": asset}


def at(db, session_id, when):
    db.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (when, session_id))


def test_open_bar_not_visible(db, ctx):
    make_bar(db, ctx["asset"], DAY1, open_=100, timeframe="1h")
    at(db, ctx["session"], DAY1 + timedelta(minutes=30))
    assert get_bars(db, ctx["session"], ctx["asset"], "1h", 10) == []


def test_closed_bar_visible(db, ctx):
    make_bar(db, ctx["asset"], DAY1, open_=100, timeframe="1h")
    at(db, ctx["session"], DAY1 + timedelta(hours=1))
    bars = get_bars(db, ctx["session"], ctx["asset"], "1h", 10)
    assert [b.open for b in bars] == [Decimal("100")]


def test_future_news_not_visible(db, ctx):
    make_news(db, DAY1 + timedelta(days=1), [ctx["asset"]])
    at(db, ctx["session"], DAY1)
    assert get_news(db, ctx["session"], ctx["asset"], 10) == []


def test_news_boundary_inclusive(db, ctx):
    make_news(db, DAY1, [ctx["asset"]], headline="on time")
    make_news(db, DAY1 + timedelta(microseconds=1), [ctx["asset"]], headline="too late")
    at(db, ctx["session"], DAY1)
    assert [n.headline for n in get_news(db, ctx["session"], ctx["asset"], 10)] == ["on time"]


def test_news_filtered_by_asset(db, ctx):
    other = make_asset(db)
    make_news(db, DAY1, [other], headline="other")
    make_news(db, DAY1, [ctx["asset"]], headline="mine")
    at(db, ctx["session"], DAY1)
    assert [n.headline for n in get_news(db, ctx["session"], ctx["asset"], 10)] == ["mine"]
    assert {n.headline for n in get_news(db, ctx["session"], None, 10)} == {"mine", "other"}


def test_bars_ordered_across_dst(db, ctx):
    # US DST started 2019-03-10; session opens shift from 14:30Z to 13:30Z.
    starts = [datetime(2019, 3, 8, 14, 30, tzinfo=UTC), datetime(2019, 3, 11, 13, 30, tzinfo=UTC),
              datetime(2019, 3, 12, 13, 30, tzinfo=UTC)]
    for i, s in enumerate(starts):
        make_bar(db, ctx["asset"], s, open_=100 + i, length=timedelta(hours=6, minutes=30))
    session = make_session(db, make_user(db), starts[0] - timedelta(days=1), sim_time=datetime(2019, 3, 13, tzinfo=UTC))
    bars = get_bars(db, session, ctx["asset"], "1d", 10)
    assert [b.bar_start for b in bars] == sorted(starts, reverse=True)


def test_latest_price_none_before_first_bar(db, ctx):
    make_bar(db, ctx["asset"], DAY1, open_=100, close=101)
    at(db, ctx["session"], DAY1)
    assert get_latest_price(db, ctx["session"], ctx["asset"]) is None
    at(db, ctx["session"], DAY1 + timedelta(days=1))
    assert get_latest_price(db, ctx["session"], ctx["asset"]) == Decimal("101")


def test_python_readers_never_query_raw_tables():
    src = (Path(__file__).resolve().parents[2] / "app" / "market" / "read.py").read_text()
    assert not re.search(r"FROM\s+(price_bar|news|news_asset)\b", src)
