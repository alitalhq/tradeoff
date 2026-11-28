"""End to end: play -> background runner -> committed ticks -> finished session."""

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.factories import make_asset, make_bar, make_order, make_portfolio, make_session, make_user

START = datetime(2019, 1, 7, tzinfo=timezone.utc)


@pytest.fixture
def live_runner(monkeypatch):
    monkeypatch.setenv("REPLAY_RUNNER_ENABLED", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def test_play_runs_session_to_the_end(committed, live_runner):
    from app.main import app

    user = make_user(committed)
    asset = make_asset(committed)
    end = START + timedelta(days=3)
    session = make_session(committed, user, START, end=end)
    committed.execute("UPDATE sim_session SET status = 'created', speed = 20 WHERE id = %s", (session,))
    portfolio = make_portfolio(committed, session, user)
    for day in range(3):
        make_bar(committed, asset, START + timedelta(days=day, hours=14, minutes=30), 100,
                 length=timedelta(hours=6, minutes=30))
    order = make_order(committed, portfolio, asset, "buy", 1, START)
    headers = {"X-User-Id": str(user)}

    with TestClient(app) as client:
        assert client.post(f"/api/sessions/{session}/play", headers=headers).status_code == 200
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            body = client.get(f"/api/sessions/{session}", headers=headers).json()
            if body["status"] == "finished":
                break
            time.sleep(0.05)

    assert body["status"] == "finished"
    assert body["sim_time"] == end.isoformat().replace("+00:00", "Z")
    status = committed.execute("SELECT status FROM trade_order WHERE id = %s", (order,)).fetchone()["status"]
    assert status == "filled"
