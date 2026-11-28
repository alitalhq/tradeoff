import pytest

from app.replay.runner import runner
from tests.api.conftest import replay_payload
from tests.factories import make_asset, make_user


@pytest.fixture
def ensured(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(runner, "ensure", calls.append)
    return calls


def url(session_id, action):
    return f"/api/sessions/{session_id}/{action}"


def set_limit(client, auth, session_id, period_no=1):
    r = client.put(f"/api/sessions/{session_id}/periods/{period_no}/limit", json={}, headers=auth)
    assert r.status_code == 204


def test_play_requires_limits(client, auth, session_id, ensured):
    r = client.post(url(session_id, "play"), headers=auth)
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "limits_required"
    assert ensured == []


def test_play_and_pause(client, auth, session_id, ensured):
    set_limit(client, auth, session_id)
    r = client.post(url(session_id, "play"), headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "running"
    assert ensured == [session_id]
    r = client.post(url(session_id, "pause"), headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "paused"


def test_step_moves_clock_one_bar(client, auth, session_id, asset, ensured):
    set_limit(client, auth, session_id)
    r = client.post(url(session_id, "step"), headers=auth)
    assert r.status_code == 200
    assert r.json()["sim_time"] == "2019-01-03T21:00:00Z" and r.json()["status"] == "paused"
    assert ensured == []


def test_step_without_limits(client, auth, session_id):
    r = client.post(url(session_id, "step"), headers=auth)
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "limits_required"


def test_step_while_running_rejected(client, auth, session_id, ensured):
    set_limit(client, auth, session_id)
    client.post(url(session_id, "play"), headers=auth)
    r = client.post(url(session_id, "step"), headers=auth)
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "invalid_state"


def test_play_finished_session(client, auth, session_id, committed):
    committed.execute("UPDATE sim_session SET status = 'finished' WHERE id = %s", (session_id,))
    r = client.post(url(session_id, "play"), headers=auth)
    assert r.status_code == 409 and r.json()["detail"]["reason"] == "session_finished"


def test_live_session_has_no_controls(client, auth):
    live = client.post("/api/sessions", json=replay_payload(mode="live", end_at=None, period_length_days=None),
                       headers=auth).json()["id"]
    for action in ("play", "pause", "step"):
        r = client.post(url(live, action), headers=auth)
        assert r.status_code == 409 and r.json()["detail"]["reason"] == "not_replay"


@pytest.mark.parametrize("speed", ["0", "0.05", "21"])
def test_speed_bounds(client, auth, session_id, speed):
    assert client.put(url(session_id, "speed"), json={"speed": speed}, headers=auth).status_code == 422


def test_set_speed(client, auth, session_id):
    r = client.put(url(session_id, "speed"), json={"speed": "4"}, headers=auth)
    assert r.status_code == 200 and r.json()["speed"] == "4.00"


def test_create_speed_bounds(client, auth):
    assert client.post("/api/sessions", json=replay_payload(speed="50"), headers=auth).status_code == 422


def test_other_users_session_is_404(client, session_id, committed):
    stranger = {"X-User-Id": str(make_user(committed))}
    for action in ("play", "pause", "step"):
        assert client.post(url(session_id, action), headers=stranger).status_code == 404
    assert client.put(url(session_id, "speed"), json={"speed": "2"}, headers=stranger).status_code == 404


def test_create_with_asset_universe(client, auth, committed):
    a, b = make_asset(committed), make_asset(committed)
    r = client.post("/api/sessions", json=replay_payload(asset_ids=[b, a, a]), headers=auth)
    assert r.status_code == 201 and r.json()["asset_ids"] == sorted([a, b])


def test_create_with_unknown_asset(client, auth):
    assert client.post("/api/sessions", json=replay_payload(asset_ids=[999999]), headers=auth).status_code == 404


def test_session_without_universe_lists_none(client, auth, session_id):
    assert client.get(f"/api/sessions/{session_id}", headers=auth).json()["asset_ids"] == []


def test_limit_resumes_awaiting_session(client, auth, session_id, committed, ensured):
    committed.execute("UPDATE sim_session SET status = 'awaiting_limits' WHERE id = %s", (session_id,))
    set_limit(client, auth, session_id)
    assert client.get(f"/api/sessions/{session_id}", headers=auth).json()["status"] == "running"
    assert ensured == [session_id]


def test_limit_for_future_period_does_not_resume(client, auth, session_id, committed, ensured):
    committed.execute("UPDATE sim_session SET status = 'awaiting_limits' WHERE id = %s", (session_id,))
    set_limit(client, auth, session_id, period_no=2)
    assert client.get(f"/api/sessions/{session_id}", headers=auth).json()["status"] == "awaiting_limits"
    assert ensured == []
