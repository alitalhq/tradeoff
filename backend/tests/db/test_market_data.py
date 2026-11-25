from datetime import datetime, timezone

import psycopg
import pytest

from tests.factories import make_asset, make_bar, make_news

D = datetime(2019, 6, 3, 13, 30, tzinfo=timezone.utc)


def test_bar_high_below_close_rejected(db):
    asset = make_asset(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        make_bar(db, asset, D, open_=100, high=101, low=99, close=105)


def test_bar_end_before_start_rejected(db):
    asset = make_asset(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO price_bar (asset_id, timeframe, bar_start, bar_end, open, high, low, close, volume) "
            "VALUES (%s, '1d', %s, %s, 1, 1, 1, 1, 0)",
            (asset, D, D),
        )


def test_bar_routed_to_year_partition(db):
    asset = make_asset(db)
    make_bar(db, asset, D, open_=100)
    row = db.execute(
        "SELECT tableoid::regclass::text AS part FROM price_bar WHERE asset_id = %s", (asset,)
    ).fetchone()
    assert row["part"] == "price_bar_2019"


def test_duplicate_news_from_same_source_rejected(db):
    sql = ("INSERT INTO news (source, external_id, headline, summary, url, published_at) "
           "VALUES ('benzinga', '42', 'h', '', 'u', %s)")
    db.execute(sql, (D,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, (D,))


def test_one_news_many_assets(db):
    a, b = make_asset(db), make_asset(db)
    news = make_news(db, D, [a, b])
    n = db.execute("SELECT count(*) AS n FROM news_asset WHERE news_id = %s", (news,)).fetchone()["n"]
    assert n == 2


def test_split_requires_ratio(db):
    asset = make_asset(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO corporate_action (asset_id, action_type, effective_at) VALUES (%s, 'split', %s)",
            (asset, D),
        )
