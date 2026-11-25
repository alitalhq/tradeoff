"""Fill pending orders from the first bar that opens after the order was placed."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import psycopg

PENDING_ORDERS_SQL = """
SELECT o.id, o.asset_id, o.side, o.order_type, o.quantity, o.limit_price, o.placed_at_sim
FROM trade_order o
JOIN portfolio p ON p.id = o.portfolio_id
WHERE p.session_id = %s AND o.status = 'pending'
ORDER BY o.id
FOR UPDATE OF o SKIP LOCKED
"""

# Only bars that started at/after the order and have closed by the session clock are eligible.
NEXT_BAR_SQL = """
SELECT b.bar_start,
       CASE
           WHEN %(order_type)s = 'market' THEN b.open
           WHEN %(side)s = 'buy' THEN least(b.open, %(limit_price)s)
           ELSE greatest(b.open, %(limit_price)s)
       END AS price
FROM sim_session s
JOIN price_bar b ON b.asset_id = %(asset_id)s AND b.timeframe = s.bar_timeframe
WHERE s.id = %(session_id)s
  AND b.bar_start >= %(placed_at)s
  AND b.bar_end <= s.sim_time
  AND (%(order_type)s = 'market'
       OR (%(side)s = 'buy' AND b.low <= %(limit_price)s)
       OR (%(side)s = 'sell' AND b.high >= %(limit_price)s))
ORDER BY b.bar_start
LIMIT 1
"""


@dataclass(frozen=True)
class FillResult:
    order_id: int
    status: Literal["filled", "rejected"]
    price: Decimal | None
    reason: str | None


def fill_pending_orders(conn: psycopg.Connection, session_id: int) -> list[FillResult]:
    results: list[FillResult] = []
    for order in conn.execute(PENDING_ORDERS_SQL, (session_id,)).fetchall():
        bar = conn.execute(NEXT_BAR_SQL, {
            "order_type": order["order_type"], "side": order["side"], "limit_price": order["limit_price"],
            "asset_id": order["asset_id"], "session_id": session_id, "placed_at": order["placed_at_sim"],
        }).fetchone()
        if bar is None:
            continue
        reason = _try_fill(conn, order["id"], bar["price"], order["quantity"], bar["bar_start"])
        if reason is None:
            results.append(FillResult(order["id"], "filled", bar["price"], None))
        else:
            conn.execute(
                "UPDATE trade_order SET status = 'rejected', reject_reason = %s WHERE id = %s",
                (reason, order["id"]),
            )
            results.append(FillResult(order["id"], "rejected", None, reason))
    return results


def _try_fill(conn: psycopg.Connection, order_id: int, price: Decimal, quantity: Decimal, at) -> str | None:
    try:
        with conn.transaction():
            conn.execute(
                "INSERT INTO fill (order_id, filled_at_sim, price, quantity) VALUES (%s, %s, %s, %s)",
                (order_id, at, price, quantity),
            )
    except psycopg.errors.CheckViolation:
        return "insufficient_cash"
    except psycopg.errors.DataError:
        # Notional beyond the cash column's range; one oversized order must not stop the batch.
        return "order_too_large"
    except psycopg.errors.RaiseException as exc:
        return exc.diag.message_primary or "rejected"
    return None
