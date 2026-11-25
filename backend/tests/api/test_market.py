from datetime import timedelta

from tests.api.conftest import T0
from tests.factories import make_bar, make_news


def test_bars_endpoint_hides_future(client, auth, session_id, asset, committed):
    make_bar(committed, asset, T0 + timedelta(days=1), open_=102)
    committed.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (T0 + timedelta(days=1), session_id))
    bars = client.get(f"/api/sessions/{session_id}/bars", params={"asset_id": asset, "timeframe": "1d"},
                      headers=auth).json()
    assert [b["open"] for b in bars] == ["100.0000"]


def test_news_endpoint_hides_future(client, auth, session_id, asset, committed):
    make_news(committed, T0, [asset], headline="now")
    make_news(committed, T0 + timedelta(hours=1), [asset], headline="later")
    news = client.get(f"/api/sessions/{session_id}/news", params={"asset_id": asset}, headers=auth).json()
    assert [n["headline"] for n in news] == ["now"]


def test_assets_listed(client, auth, asset):
    assert asset in [a["id"] for a in client.get("/api/assets", headers=auth).json()]
