def test_place_order_returns_pending(client, auth, session_id, asset):
    r = client.post(f"/api/sessions/{session_id}/orders",
                    json={"asset_id": asset, "side": "buy", "quantity": "2"}, headers=auth)
    assert r.status_code == 201
    assert r.json()["status"] == "pending" and r.json()["quantity"] == "2.0000"
    listed = client.get(f"/api/sessions/{session_id}/orders", headers=auth).json()
    assert [o["id"] for o in listed] == [r.json()["id"]]


def test_order_over_limit_returns_409_with_reason(client, auth, session_id, asset):
    r = client.put(f"/api/sessions/{session_id}/periods/1/limit", json={"max_orders": 1}, headers=auth)
    assert r.status_code == 204
    order = {"asset_id": asset, "side": "buy", "quantity": "1"}
    assert client.post(f"/api/sessions/{session_id}/orders", json=order, headers=auth).status_code == 201
    r = client.post(f"/api/sessions/{session_id}/orders", json=order, headers=auth)
    assert r.status_code == 409 and r.json() == {"detail": {"reason": "period_limit_exceeded"}}


def test_limit_for_unknown_period_is_404(client, auth, session_id):
    assert client.put(f"/api/sessions/{session_id}/periods/9/limit", json={}, headers=auth).status_code == 404


def test_unknown_asset_is_404(client, auth, session_id):
    r = client.post(f"/api/sessions/{session_id}/orders",
                    json={"asset_id": 999999, "side": "buy", "quantity": "1"}, headers=auth)
    assert r.status_code == 404


def test_limit_order_requires_price(client, auth, session_id, asset):
    r = client.post(f"/api/sessions/{session_id}/orders",
                    json={"asset_id": asset, "side": "buy", "quantity": "1", "order_type": "limit"},
                    headers=auth)
    assert r.status_code == 422


def test_money_serialized_as_string(client, auth, session_id):
    body = client.get(f"/api/sessions/{session_id}/portfolio", headers=auth).json()
    assert body == {"cash": "10000.00", "positions": []}
