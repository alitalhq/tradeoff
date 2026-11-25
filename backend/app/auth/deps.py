from fastapi import Depends, HTTPException, Request

from app.api.deps import Conn
from app.config import get_settings


def get_current_user(request: Request, conn: Conn) -> int:
    """Temporary development auth: trusts X-User-Id only when APP_ENV is explicitly dev or test.

    The auth plan replaces this body with real session-cookie auth; the signature stays.
    """
    if get_settings().app_env not in ("dev", "test"):
        raise HTTPException(status_code=501, detail="authentication not implemented")
    return _resolve_user(conn, request.headers.get("X-User-Id"))


def _resolve_user(conn, raw: str | None) -> int:
    if raw is None or not raw.isdigit():
        raise HTTPException(status_code=401, detail="missing user")
    row = conn.execute("SELECT id FROM app_user WHERE id = %s", (int(raw),)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return row["id"]


def ws_user(conn, user_id: str | None) -> int | None:
    """WebSocket variant (browsers cannot set headers on WS): user id comes from the query string."""
    if get_settings().app_env not in ("dev", "test"):
        return None
    try:
        return _resolve_user(conn, user_id)
    except HTTPException:
        return None
