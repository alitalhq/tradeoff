"""Background clock: one asyncio task per running replay session.

Ticks run in a worker thread (they do blocking DB work) and messages are published only after
the tick has committed. Safe to `ensure` from request threads.
"""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

from app.db import connect
from app.replay.engine import ReplayError, TickResult, run_tick
from app.ws.hub import hub

log = logging.getLogger(__name__)

MAX_FAILURES = 3
RETRY_SECONDS = 1.0


def pause_session(session_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE sim_session SET status = 'paused' WHERE id = %s AND status = 'running'",
                     (session_id,))


def running_session_ids() -> list[int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM sim_session WHERE mode = 'replay' AND status = 'running' ORDER BY id"
        ).fetchall()
    return [r["id"] for r in rows]


class ReplayRunner:
    def __init__(self, tick: Callable[[int], TickResult] = run_tick, publish=hub.publish,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 pause: Callable[[int], None] = pause_session) -> None:
        self._tick, self._publish, self._sleep, self._pause = tick, publish, sleep, pause
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: dict[int, asyncio.Task] = {}
        self._lock = threading.Lock()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def ensure(self, session_id: int) -> None:
        """Start the session's loop unless it is already running. No-op when the runner is not attached."""
        loop = self._loop
        if loop is None:
            return
        try:
            on_loop = asyncio.get_running_loop() is loop
        except RuntimeError:
            on_loop = False
        if on_loop:
            self._start(session_id)
        else:
            loop.call_soon_threadsafe(self._start, session_id)

    def _start(self, session_id: int) -> None:
        with self._lock:
            task = self._tasks.get(session_id)
            if task is None or task.done():
                self._tasks[session_id] = asyncio.get_running_loop().create_task(self._run(session_id))

    async def wait(self, session_id: int) -> None:
        task = self._tasks.get(session_id)
        if task is not None:
            await task

    async def _run(self, session_id: int) -> None:
        failures = 0
        while True:
            try:
                result = await asyncio.to_thread(self._tick, session_id)
            except ReplayError:
                return
            except Exception:
                failures += 1
                log.exception("replay tick failed for session %s (%s/%s)", session_id, failures, MAX_FAILURES)
                if failures >= MAX_FAILURES:
                    await asyncio.to_thread(self._pause, session_id)
                    return
                await self._sleep(RETRY_SECONDS)
                continue
            failures = 0
            for msg in result.messages:
                self._publish(session_id, msg)
            if result.status != "running":
                return
            await self._sleep(1 / float(result.speed))

    async def resume_running(self) -> None:
        for session_id in await asyncio.to_thread(running_session_ids):
            self.ensure(session_id)

    async def stop_all(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._loop = None


runner = ReplayRunner()
