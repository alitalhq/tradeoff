from pathlib import Path

from app.contracts import export_contracts

REPO_CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"


def test_contracts_up_to_date(tmp_path):
    export_contracts(tmp_path)
    for name in ("openapi.json", "ws-schema.json"):
        assert (tmp_path / name).read_text() == (REPO_CONTRACTS / name).read_text(), name
