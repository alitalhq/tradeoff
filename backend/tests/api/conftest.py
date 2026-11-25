from datetime import datetime, timezone

import pytest

from tests.factories import make_asset, make_bar, make_user

T0 = datetime(2019, 1, 2, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def user(committed):
    return make_user(committed)


@pytest.fixture
def auth(user):
    return {"X-User-Id": str(user)}


@pytest.fixture
def asset(committed):
    asset_id = make_asset(committed)
    make_bar(committed, asset_id, T0, open_=100, close=101)
    return asset_id


def replay_payload(**overrides):
    payload = {
        "mode": "replay",
        "bar_timeframe": "1d",
        "start_at": "2019-01-02T21:00:00Z",
        "end_at": "2019-02-01T21:00:00Z",
        "initial_cash": "10000",
        "period_length_days": 15,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def session_id(client, auth):
    return client.post("/api/sessions", json=replay_payload(), headers=auth).json()["id"]
