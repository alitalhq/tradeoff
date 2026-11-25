from datetime import timedelta

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_conn
from app.api.schemas import PeriodLimitIn, PortfolioOut, SessionCreate, SessionOut
from app.auth.deps import get_current_user

router = APIRouter(prefix="/sessions", tags=["sessions"])

SESSION_SQL = """
SELECT s.id, s.mode, s.bar_timeframe, s.start_at, s.end_at, s.sim_time, s.speed, s.status,
       s.initial_cash, s.period_length_days, p.id AS portfolio_id
FROM sim_session s
JOIN portfolio p ON p.session_id = s.id AND p.user_id = s.owner_user_id
WHERE s.id = %s AND s.owner_user_id = %s
"""


def load_session(conn: psycopg.Connection, session_id: int, user_id: int) -> dict:
    """The user's own session or 404 (never 403, so session ids do not leak)."""
    row = conn.execute(SESSION_SQL, (session_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return row


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionOut)
def create_session(body: SessionCreate, user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    session_id = conn.execute(
        "INSERT INTO sim_session (owner_user_id, mode, bar_timeframe, start_at, end_at, sim_time, speed, "
        "status, initial_cash, period_length_days) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'created', %s, %s) RETURNING id",
        (user_id, body.mode, body.bar_timeframe, body.start_at, body.end_at, body.start_at, body.speed,
         body.initial_cash, body.period_length_days),
    ).fetchone()["id"]
    conn.execute("INSERT INTO portfolio (session_id, user_id) VALUES (%s, %s)", (session_id, user_id))

    if body.period_length_days and body.end_at:
        step = timedelta(days=body.period_length_days)
        starts, number = body.start_at, 1
        while starts < body.end_at:
            ends = min(starts + step, body.end_at)
            conn.execute(
                "INSERT INTO trading_period (session_id, period_no, starts_at, ends_at) VALUES (%s, %s, %s, %s)",
                (session_id, number, starts, ends),
            )
            starts, number = ends, number + 1
    return load_session(conn, session_id, user_id)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    return load_session(conn, session_id, user_id)


@router.get("/{session_id}/portfolio", response_model=PortfolioOut)
def get_portfolio(session_id: int, user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    session = load_session(conn, session_id, user_id)
    cash = conn.execute("SELECT cash FROM portfolio WHERE id = %s", (session["portfolio_id"],)).fetchone()["cash"]
    positions = conn.execute(
        "SELECT pos.asset_id, a.symbol, pos.net_qty, pos.avg_cost, "
        "       latest_price_as_of(%s, pos.asset_id) AS last_price "
        "FROM position pos JOIN asset a ON a.id = pos.asset_id "
        "WHERE pos.portfolio_id = %s ORDER BY a.symbol",
        (session_id, session["portfolio_id"]),
    ).fetchall()
    return {"cash": cash, "positions": positions}


@router.put("/{session_id}/periods/{period_no}/limit", status_code=status.HTTP_204_NO_CONTENT)
def set_period_limit(session_id: int, period_no: int, body: PeriodLimitIn,
                     user_id: int = Depends(get_current_user), conn=Depends(get_conn)):
    session = load_session(conn, session_id, user_id)
    period = conn.execute(
        "SELECT id, ends_at FROM trading_period WHERE session_id = %s AND period_no = %s",
        (session_id, period_no),
    ).fetchone()
    if period is None:
        raise HTTPException(status_code=404, detail="period not found")
    if period["ends_at"] <= session["sim_time"]:
        raise HTTPException(status_code=409, detail={"reason": "period_closed"})
    conn.execute(
        "INSERT INTO period_limit (portfolio_id, period_id, max_buy_amount, max_sell_amount, max_orders) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (portfolio_id, period_id) DO UPDATE SET max_buy_amount = EXCLUDED.max_buy_amount, "
        "max_sell_amount = EXCLUDED.max_sell_amount, max_orders = EXCLUDED.max_orders, set_at = now()",
        (session["portfolio_id"], period["id"], body.max_buy_amount, body.max_sell_amount, body.max_orders),
    )
