import psycopg
import pytest


def _user(db, email="trader@example.com"):
    return db.execute(
        "INSERT INTO app_user (email, password_hash, display_name) VALUES (%s, 'x', 'T') RETURNING id",
        (email,),
    ).fetchone()["id"]


def _provider(db, name="Anthropic"):
    return db.execute("SELECT id FROM llm_provider WHERE name = %s", (name,)).fetchone()["id"]


def _sector(db, name="Technology"):
    return db.execute("INSERT INTO sector (name) VALUES (%s) RETURNING id", (name,)).fetchone()["id"]


def _exchange(db, code="NASDAQ"):
    return db.execute("SELECT id FROM exchange WHERE code = %s", (code,)).fetchone()["id"]


def _asset(db, symbol, sector_id):
    return db.execute(
        "INSERT INTO asset (symbol, name, sector_id, exchange_id) VALUES (%s, %s, %s, %s) RETURNING id",
        (symbol, symbol + " Inc", sector_id, _exchange(db)),
    ).fetchone()["id"]


def test_asset_symbol_unique(db):
    sector = _sector(db)
    _asset(db, "AAPL", sector)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _asset(db, "AAPL", sector)


def test_email_case_insensitive(db):
    _user(db, "A@x.com")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _user(db, "a@x.com")


def test_credential_one_per_provider(db):
    user = _user(db)
    sql = ("INSERT INTO user_api_credential (user_id, provider_id, encrypted_key, key_last4) "
           "VALUES (%s, %s, '\\x00', 'abcd')")
    db.execute(sql, (user, _provider(db)))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, (user, _provider(db)))


def test_delete_user_cascades_credentials(db):
    user = _user(db)
    db.execute(
        "INSERT INTO user_api_credential (user_id, provider_id, encrypted_key, key_last4) "
        "VALUES (%s, %s, '\\x00', 'abcd')",
        (user, _provider(db)),
    )
    db.execute("DELETE FROM app_user WHERE id = %s", (user,))
    assert db.execute("SELECT count(*) AS n FROM user_api_credential").fetchone()["n"] == 0


def test_sector_in_use_cannot_be_deleted(db):
    sector = _sector(db)
    _asset(db, "MSFT", sector)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("DELETE FROM sector WHERE id = %s", (sector,))


def test_seeded_providers_and_exchanges(db):
    names = {r["name"] for r in db.execute("SELECT name FROM llm_provider").fetchall()}
    assert names == {"Anthropic", "OpenAI", "Google"}
    codes = {r["code"] for r in db.execute("SELECT code FROM exchange").fetchall()}
    assert codes == {"NASDAQ", "NYSE"}
