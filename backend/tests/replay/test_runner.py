import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.config import Settings
from app.replay.engine import ReplayError, TickResult
from app.replay.runner import ReplayRunner
from app.ws.messages import ClockMessage

T = datetime(2019, 1, 7, tzinfo=timezone.utc)


def result(status, speed="2"):
    return TickResult(status, T, Decimal(speed), [ClockMessage(sim_time=T, status=status)])


class Fakes:
    def __init__(self, results):
        self.results = list(results)
        self.ticks, self.published, self.sleeps, self.paused = [], [], [], []

    def tick(self, sid):
        self.ticks.append(sid)
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def publish(self, sid, msg):
        self.published.append((sid, msg.status))

    async def sleep(self, seconds):
        self.sleeps.append(seconds)

    def pause(self, sid):
        self.paused.append(sid)

    def runner(self):
        return ReplayRunner(tick=self.tick, publish=self.publish, sleep=self.sleep, pause=self.pause)


async def _run(runner, sid=1):
    runner.attach(asyncio.get_running_loop())
    runner.ensure(sid)
    await runner.wait(sid)


def test_runner_loops_until_not_running():
    f = Fakes([result("running"), result("running"), result("finished")])
    asyncio.run(_run(f.runner()))
    assert f.ticks == [1, 1, 1]
    assert f.published == [(1, "running"), (1, "running"), (1, "finished")]
    assert f.sleeps == [0.5, 0.5]


def test_runner_stops_on_replay_error():
    f = Fakes([ReplayError("session_finished")])
    asyncio.run(_run(f.runner()))
    assert f.ticks == [1] and f.published == [] and f.paused == []


def test_ensure_is_idempotent():
    f = Fakes([result("running"), result("paused")])

    async def go():
        runner = f.runner()
        runner.attach(asyncio.get_running_loop())
        runner.ensure(1)
        runner.ensure(1)
        await runner.wait(1)

    asyncio.run(go())
    assert f.ticks == [1, 1]


def test_pauses_after_three_failures():
    f = Fakes([RuntimeError("db down")] * 3)
    asyncio.run(_run(f.runner()))
    assert f.ticks == [1, 1, 1] and f.paused == [1]


def test_failure_counter_resets_after_success():
    f = Fakes([RuntimeError("x"), RuntimeError("x"), result("running"), RuntimeError("x"), result("paused")])
    asyncio.run(_run(f.runner()))
    assert f.paused == []


def test_ensure_without_loop_is_noop():
    ReplayRunner(tick=lambda sid: None).ensure(1)


def test_runner_disabled_in_test_env():
    assert Settings(app_env="test").runner_enabled is False
    assert Settings(app_env="prod").runner_enabled is True
    assert Settings(app_env="test", replay_runner_enabled=True).runner_enabled is True


def test_resume_running_picks_up_running_replays(committed):
    from tests.factories import make_session, make_user

    user = make_user(committed)
    running = make_session(committed, user, T)
    paused = make_session(committed, user, T)
    committed.execute("UPDATE sim_session SET status = 'paused' WHERE id = %s", (paused,))
    make_session(committed, user, T, mode="live")
    f = Fakes([result("paused")])

    async def go():
        runner = f.runner()
        runner.attach(asyncio.get_running_loop())
        await runner.resume_running()
        await runner.wait(running)

    asyncio.run(go())
    assert f.ticks == [running]
