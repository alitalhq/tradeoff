from tests.api.conftest import replay_payload
from tests.factories import make_user


def test_create_replay_session_creates_periods(client, auth, committed):
    r = client.post("/api/sessions", json=replay_payload(), headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["sim_time"] == "2019-01-02T21:00:00Z"
    assert body["portfolio_id"] > 0
    periods = committed.execute(
        "SELECT period_no FROM trading_period WHERE session_id = %s ORDER BY period_no", (body["id"],)
    ).fetchall()
    assert [p["period_no"] for p in periods] == [1, 2]


def test_get_session(client, auth, session_id):
    assert client.get(f"/api/sessions/{session_id}", headers=auth).json()["id"] == session_id


def test_other_users_session_is_404(client, session_id, committed):
    stranger = make_user(committed)
    r = client.get(f"/api/sessions/{session_id}", headers={"X-User-Id": str(stranger)})
    assert r.status_code == 404


def test_naive_datetime_rejected(client, auth):
    r = client.post("/api/sessions", json=replay_payload(start_at="2019-01-02T21:00:00"), headers=auth)
    assert r.status_code == 422


def test_replay_requires_end_after_start(client, auth):
    r = client.post("/api/sessions", json=replay_payload(end_at="2019-01-01T00:00:00Z"), headers=auth)
    assert r.status_code == 422


def test_missing_user_header_is_401(client):
    assert client.post("/api/sessions", json=replay_payload()).status_code == 401


def test_prod_without_auth_returns_501(client, auth, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        assert client.post("/api/sessions", json=replay_payload(), headers=auth).status_code == 501
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_too_many_periods_rejected(client, auth):
    r = client.post("/api/sessions", json=replay_payload(end_at="2100-01-01T00:00:00Z", period_length_days=1),
                    headers=auth)
    assert r.status_code == 422


def test_replay_span_capped(client, auth):
    r = client.post("/api/sessions", json=replay_payload(end_at="2040-01-01T00:00:00Z", period_length_days=None),
                    headers=auth)
    assert r.status_code == 422


def test_last_period_truncated_to_end(client, auth, committed):
    body = client.post("/api/sessions", json=replay_payload(end_at="2019-01-25T21:00:00Z"), headers=auth).json()
    rows = committed.execute(
        "SELECT period_no, ends_at FROM trading_period WHERE session_id = %s ORDER BY period_no", (body["id"],)
    ).fetchall()
    assert [r["period_no"] for r in rows] == [1, 2]
    assert rows[-1]["ends_at"].isoformat() == "2019-01-25T21:00:00+00:00"


def test_session_lists_its_trading_periods(client, auth, session_id):
    periods = client.get(f"/api/sessions/{session_id}", headers=auth).json()["periods"]
    assert [p["period_no"] for p in periods] == [1, 2]
    assert periods[0]["starts_at"] == "2019-01-02T21:00:00Z"
