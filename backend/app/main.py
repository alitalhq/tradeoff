from fastapi import FastAPI

from app.api import market, orders, sessions
from app.db import connect
from app.ws import routes as ws_routes

app = FastAPI(title="TradeOff", version="0.1.0")
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
