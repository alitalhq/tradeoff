from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.auth.deps import ws_user
from app.db import connect
from app.ws.hub import hub

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_socket(websocket: WebSocket, session_id: int, user_id: str | None = None):
    with connect() as conn:
        user = ws_user(conn, user_id)
        owns = user is not None and conn.execute(
            "SELECT 1 FROM sim_session WHERE id = %s AND owner_user_id = %s", (session_id, user)
        ).fetchone() is not None
    if not owns:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    queue = hub.subscribe(session_id)
    try:
        while True:
            await websocket.send_text(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(session_id, queue)
