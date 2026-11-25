from fastapi import APIRouter, Depends, Query

from app.api.deps import Conn
from app.api.schemas import AssetOut, Timeframe
from app.api.sessions import load_session
from app.auth.deps import get_current_user
from app.market.models import Bar, NewsItem
from app.market.read import get_bars, get_news

router = APIRouter(tags=["market"])


@router.get("/sessions/{session_id}/bars", response_model=list[Bar])
def session_bars(*, session_id: int, asset_id: int, timeframe: Timeframe = "1d",
                 limit: int = Query(default=200, ge=1, le=5000),
                 user_id: int = Depends(get_current_user), conn: Conn):
    """Bars visible at the session clock, oldest first (chart order)."""
    load_session(conn, session_id, user_id)
    return list(reversed(get_bars(conn, session_id, asset_id, timeframe, limit)))


@router.get("/sessions/{session_id}/news", response_model=list[NewsItem])
def session_news(*, session_id: int, asset_id: int | None = None, limit: int = Query(default=50, ge=1, le=500),
                 user_id: int = Depends(get_current_user), conn: Conn):
    """News published by the session clock, newest first."""
    load_session(conn, session_id, user_id)
    return get_news(conn, session_id, asset_id, limit)


@router.get("/assets", response_model=list[AssetOut])
def list_assets(*, user_id: int = Depends(get_current_user), conn: Conn):
    return conn.execute(
        "SELECT a.id, a.symbol, a.name, s.name AS sector FROM asset a JOIN sector s ON s.id = a.sector_id "
        "WHERE a.is_active ORDER BY a.symbol"
    ).fetchall()
