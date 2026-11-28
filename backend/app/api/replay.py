"""Replay controls: play, pause, single step and speed."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import Conn
from app.api.schemas import SessionOut, SpeedIn
from app.api.sessions import load_session
from app.auth.deps import get_current_user
from app.replay.engine import ReplayError, missing_limit, run_tick
from app.replay.runner import runner
from app.ws.hub import hub
from app.ws.messages import ClockMessage

router = APIRouter(prefix="/sessions/{session_id}", tags=["replay"])

CONFLICT = {409: {"description": "The session cannot do this right now"}}


def _conflict(reason: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"reason": reason})


def _lock_replay(conn, session_id: int) -> dict:
    row = conn.execute("SELECT mode, status, sim_time FROM sim_session WHERE id = %s FOR UPDATE",
                       (session_id,)).fetchone()
    if row["mode"] != "replay":
        raise _conflict("not_replay")
    if row["status"] == "finished":
        raise _conflict("session_finished")
    return row


def _set_status(conn, session_id: int, new_status: str, background: BackgroundTasks) -> None:
    sim_time = conn.execute("UPDATE sim_session SET status = %s WHERE id = %s RETURNING sim_time",
                            (new_status, session_id)).fetchone()["sim_time"]
    # Background tasks run after the response transaction has committed.
    background.add_task(hub.publish, session_id, ClockMessage(sim_time=sim_time, status=new_status))


@router.post("/play", response_model=SessionOut, responses=CONFLICT)
def play(*, session_id: int, background: BackgroundTasks, user_id: int = Depends(get_current_user), conn: Conn):
    load_session(conn, session_id, user_id)
    row = _lock_replay(conn, session_id)
    if row["status"] == "awaiting_limits" or missing_limit(conn, session_id, row["sim_time"]) is not None:
        raise _conflict("limits_required")
    if row["status"] != "running":
        _set_status(conn, session_id, "running", background)
    background.add_task(runner.ensure, session_id)
    return load_session(conn, session_id, user_id)


@router.post("/pause", response_model=SessionOut, responses=CONFLICT)
def pause(*, session_id: int, background: BackgroundTasks, user_id: int = Depends(get_current_user), conn: Conn):
    load_session(conn, session_id, user_id)
    row = _lock_replay(conn, session_id)
    if row["status"] in ("running", "awaiting_limits"):
        _set_status(conn, session_id, "paused", background)
    return load_session(conn, session_id, user_id)


@router.post("/step", response_model=SessionOut, responses=CONFLICT)
def step(*, session_id: int, user_id: int = Depends(get_current_user), conn: Conn):
    load_session(conn, session_id, user_id)
    # Release the request transaction so the tick's own connection can take the session lock.
    conn.commit()
    try:
        result = run_tick(session_id, manual=True)
    except ReplayError as exc:
        raise _conflict(exc.reason) from exc
    for msg in result.messages:
        hub.publish(session_id, msg)
    return load_session(conn, session_id, user_id)


@router.put("/speed", response_model=SessionOut, responses=CONFLICT)
def set_speed(*, session_id: int, body: SpeedIn, user_id: int = Depends(get_current_user), conn: Conn):
    load_session(conn, session_id, user_id)
    if conn.execute("SELECT mode FROM sim_session WHERE id = %s", (session_id,)).fetchone()["mode"] != "replay":
        raise _conflict("not_replay")
    conn.execute("UPDATE sim_session SET speed = %s WHERE id = %s", (body.speed, session_id))
    return load_session(conn, session_id, user_id)
