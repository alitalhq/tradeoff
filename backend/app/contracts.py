"""Export the HTTP and WebSocket contracts the frontend generates its types from."""

import json
from pathlib import Path

from app.main import app
from app.ws.messages import server_message_adapter

REPO_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def export_contracts(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "openapi.json").write_text(_dump(app.openapi()))
    (target / "ws-schema.json").write_text(_dump(server_message_adapter.json_schema(mode="serialization")))


if __name__ == "__main__":
    export_contracts(REPO_CONTRACTS)
    print(f"wrote {REPO_CONTRACTS}")
