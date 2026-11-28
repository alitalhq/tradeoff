"""One replay tick: move the session clock to the next closed bar and apply what happened on the way.

`advance` runs inside the caller's transaction and never commits. `run_tick` wraps it in its own
connection and commits, so the returned messages describe state that is already durable.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import psycopg

from app.db import connect
from app.market.models import Bar, NewsItem
from app.trading.fills import fill_pending_orders
from app.ws.messages import (AdjustmentMessage, BarMessage, ClockMessage, FillMessage, NewsMessage,
                             PeriodMessage, ServerMessage)


class ReplayError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TickResult:
    status: str
    sim_time: datetime
    speed: Decimal
    messages: list[ServerMessage]


UNIVERSE = """
(NOT EXISTS (SELECT 1 FROM session_asset sa WHERE sa.session_id = %(sid)s)
 OR EXISTS (SELECT 1 FROM session_asset sa WHERE sa.session_id = %(sid)s AND sa.asset_id = {col}))
"""

NEXT_BAR_END_SQL = f"""
SELECT min(b.bar_end) AS t
FROM price_bar b
WHERE b.timeframe = %(tf)s AND b.bar_end > %(now)s AND {UNIVERSE.format(col="b.asset_id")}
"""

# The window ends at the new clock, so nothing here is ahead of what the session may see.
BARS_SQL = f"""
SELECT b.* FROM price_bar b
WHERE b.timeframe = %(tf)s AND b.bar_end > %(old)s AND b.bar_end <= %(new)s
  AND {UNIVERSE.format(col="b.asset_id")}
ORDER BY b.bar_end, b.asset_id
"""

NEWS_SQL = f"""
SELECT n.* FROM news n
WHERE n.published_at > %(old)s AND n.published_at <= %(new)s
  AND (NOT EXISTS (SELECT 1 FROM session_asset sa WHERE sa.session_id = %(sid)s)
       OR EXISTS (SELECT 1 FROM news_asset na JOIN session_asset sa ON sa.asset_id = na.asset_id
                  WHERE na.news_id = n.id AND sa.session_id = %(sid)s))
ORDER BY n.published_at, n.id
"""

# Period containing `at` whose owner portfolio has no limit row yet.
MISSING_LIMIT_SQL = """
SELECT tp.period_no, tp.starts_at, tp.ends_at
FROM trading_period tp
JOIN sim_session s ON s.id = tp.session_id
JOIN portfolio p ON p.session_id = s.id AND p.user_id = s.owner_user_id
WHERE tp.session_id = %(sid)s AND %(at)s >= tp.starts_at AND %(at)s < tp.ends_at
  AND NOT EXISTS (SELECT 1 FROM period_limit pl WHERE pl.period_id = tp.id AND pl.portfolio_id = p.id)
"""


def _missing_limit(conn: psycopg.Connection, session_id: int, at: datetime) -> dict | None:
    return conn.execute(MISSING_LIMIT_SQL, {"sid": session_id, "at": at}).fetchone()


def _period_message(period: dict, awaiting: bool) -> PeriodMessage:
    return PeriodMessage(period_no=period["period_no"], starts_at=period["starts_at"],
                         ends_at=period["ends_at"], awaiting_limits=awaiting)


def advance(conn: psycopg.Connection, session_id: int, *, manual: bool = False) -> TickResult:
    """Advance one step. `manual` is a user's single step on a created/paused session."""
    s = conn.execute("SELECT * FROM sim_session WHERE id = %s FOR UPDATE", (session_id,)).fetchone()
    if s is None or s["mode"] != "replay":
        raise ReplayError("not_replay")
    if s["status"] == "finished":
        raise ReplayError("session_finished")
    if manual and s["status"] not in ("created", "paused"):
        raise ReplayError("invalid_state")
    if not manual and s["status"] != "running":
        return TickResult(s["status"], s["sim_time"], s["speed"], [])

    old = s["sim_time"]
    blocked = _missing_limit(conn, session_id, old)
    if blocked is not None:
        if manual:
            raise ReplayError("limits_required")
        conn.execute("UPDATE sim_session SET status = 'awaiting_limits' WHERE id = %s", (session_id,))
        return TickResult("awaiting_limits", old, s["speed"], [
            ClockMessage(sim_time=old, status="awaiting_limits"), _period_message(blocked, True)])

    params = {"sid": session_id, "tf": s["bar_timeframe"], "now": old}
    candidates = [s["end_at"], conn.execute(NEXT_BAR_END_SQL, params).fetchone()["t"],
                  conn.execute("SELECT min(starts_at) AS t FROM trading_period WHERE session_id = %s "
                               "AND starts_at > %s", (session_id, old)).fetchone()["t"]]
    new = min(t for t in candidates if t is not None)
    conn.execute("UPDATE sim_session SET sim_time = %s WHERE id = %s", (new, session_id))

    adjustments = conn.execute(
        "SELECT ap.*, ca.asset_id, ca.action_type FROM apply_corporate_actions(%s, %s, %s) ap "
        "JOIN corporate_action ca ON ca.id = ap.corporate_action_id", (session_id, old, new),
    ).fetchall()
    fills = fill_pending_orders(conn, session_id)

    window = {"sid": session_id, "tf": s["bar_timeframe"], "old": old, "new": new}
    bars = conn.execute(BARS_SQL, window).fetchall()
    news = conn.execute(NEWS_SQL, window).fetchall()

    status = "paused" if manual else s["status"]
    period_messages: list[ServerMessage] = []
    started = conn.execute(
        "SELECT period_no, starts_at, ends_at FROM trading_period WHERE session_id = %s AND starts_at = %s",
        (session_id, new),
    ).fetchone()
    if new >= s["end_at"]:
        status = "finished"
    elif started is not None:
        awaiting = _missing_limit(conn, session_id, new) is not None
        period_messages.append(_period_message(started, awaiting))
        if awaiting and not manual:
            status = "awaiting_limits"
    if status != s["status"]:
        conn.execute("UPDATE sim_session SET status = %s WHERE id = %s", (status, session_id))

    messages: list[ServerMessage] = [ClockMessage(sim_time=new, status=status)]
    messages += [BarMessage(asset_id=b["asset_id"], bar=Bar.model_validate(b)) for b in bars]
    messages += [NewsMessage(item=NewsItem.model_validate(n)) for n in news]
    messages += [AdjustmentMessage(portfolio_id=a["portfolio_id"], asset_id=a["asset_id"],
                                   action_type=a["action_type"], qty_delta=a["qty_delta"],
                                   cash_delta=a["cash_delta"]) for a in adjustments]
    messages += [FillMessage(order_id=f.order_id, status=f.status, price=f.price, reason=f.reason)
                 for f in fills]
    messages += period_messages
    return TickResult(status, new, s["speed"], messages)


def run_tick(session_id: int, *, manual: bool = False) -> TickResult:
    """One committed tick on a dedicated connection. Raises ReplayError without committing anything."""
    with connect() as conn:
        with conn.transaction():
            return advance(conn, session_id, manual=manual)
