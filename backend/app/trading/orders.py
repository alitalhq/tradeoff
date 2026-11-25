from decimal import Decimal
from typing import Literal

import psycopg

from app.trading.errors import OrderRejected

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


def place_order(conn: psycopg.Connection, portfolio_id: int, asset_id: int, side: Side, quantity: Decimal,
                order_type: OrderType = "market", limit_price: Decimal | None = None,
                decision_id: int | None = None) -> int:
    """Insert a pending order stamped with the session clock. Raises OrderRejected on a rule violation."""
    try:
        with conn.transaction():
            row = conn.execute(
                """
                INSERT INTO trade_order (portfolio_id, asset_id, side, order_type, quantity, limit_price,
                                         placed_at_sim, decision_id)
                SELECT p.id, %s, %s, %s, %s, %s, s.sim_time, %s
                FROM portfolio p JOIN sim_session s ON s.id = p.session_id
                WHERE p.id = %s
                RETURNING id
                """,
                (asset_id, side, order_type, quantity, limit_price, decision_id, portfolio_id),
            ).fetchone()
    except psycopg.errors.RaiseException as exc:
        raise OrderRejected(exc.diag.message_primary or "rejected") from exc
    if row is None:
        raise OrderRejected("portfolio_not_found")
    return row["id"]
