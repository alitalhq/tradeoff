from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Conn
from app.api.schemas import OrderCreate, OrderOut
from app.api.sessions import load_session
from app.auth.deps import get_current_user
from app.trading.errors import OrderRejected
from app.trading.orders import place_order

router = APIRouter(prefix="/sessions/{session_id}/orders", tags=["orders"])

ORDER_COLUMNS = "id, asset_id, side, order_type, quantity, limit_price, placed_at_sim, status, reject_reason"


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderOut,
             responses={409: {"description": "Order rejected by a trading rule"}})
def create_order(*, session_id: int, body: OrderCreate, user_id: int = Depends(get_current_user),
                 conn: Conn):
    session = load_session(conn, session_id, user_id)
    if conn.execute("SELECT 1 FROM asset WHERE id = %s", (body.asset_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="asset not found")
    try:
        order_id = place_order(conn, session["portfolio_id"], body.asset_id, body.side, body.quantity,
                               body.order_type, body.limit_price)
    except OrderRejected as exc:
        raise HTTPException(status_code=409, detail={"reason": exc.reason}) from exc
    return conn.execute(f"SELECT {ORDER_COLUMNS} FROM trade_order WHERE id = %s", (order_id,)).fetchone()


@router.get("", response_model=list[OrderOut])
def list_orders(*, session_id: int, user_id: int = Depends(get_current_user), conn: Conn):
    session = load_session(conn, session_id, user_id)
    return conn.execute(
        f"SELECT {ORDER_COLUMNS} FROM trade_order WHERE portfolio_id = %s ORDER BY id",
        (session["portfolio_id"],),
    ).fetchall()
