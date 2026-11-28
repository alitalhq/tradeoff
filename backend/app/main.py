import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import market, orders, sessions
from app.config import get_settings
from app.db import connect
from app.replay.runner import runner
from app.ws import routes as ws_routes



@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().runner_enabled:
        runner.attach(asyncio.get_running_loop())
        await runner.resume_running()
    yield
    await runner.stop_all()


app = FastAPI(title="TradeOff", version="0.1.0", lifespan=lifespan)
app.include_router(sessions.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(ws_routes.router)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "db": db_status}
