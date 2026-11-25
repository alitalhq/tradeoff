from fastapi import FastAPI

from app.db import connect

app = FastAPI(title="TradeOff")


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "db": db_status}
