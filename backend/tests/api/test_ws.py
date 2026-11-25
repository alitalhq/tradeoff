from datetime import datetime, timezone

from app.ws.hub import hub
from app.ws.messages import ClockMessage


def test_ws_receives_published_message(client, user, session_id):
    with client.websocket_connect(f"/ws/sessions/{session_id}?user_id={user}") as ws:
        hub.publish(session_id, ClockMessage(sim_time=datetime(2019, 1, 3, tzinfo=timezone.utc), status="running"))
        assert ws.receive_json() == {"type": "clock", "sim_time": "2019-01-03T00:00:00Z", "status": "running"}
