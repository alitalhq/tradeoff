from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from tests.factories import (add_competitor, make_agent, make_asset, make_competition, make_credential,
                             make_model, make_session, make_user)

T0 = datetime(2019, 1, 2, 21, 0, tzinfo=timezone.utc)


@pytest.fixture
def arena(db):
    owner = make_user(db)
    session = make_session(db, owner, T0)
    competition = make_competition(db, owner, session)
    model = make_model(db, cutoff="2018-06-01")
    credential = make_credential(db, owner)
    agent = make_agent(db, owner, model, credential)
    return {"owner": owner, "session": session, "competition": competition, "model": model,
            "credential": credential, "agent": agent}


def _decision(db, competitor_id, sim_time, context_max_ts):
    return db.execute(
        "INSERT INTO agent_decision (competitor_id, sim_time, context_hash, context_max_ts) "
        "VALUES (%s, %s, '\\x01', %s) RETURNING id",
        (competitor_id, sim_time, context_max_ts),
    ).fetchone()["id"]


def test_decision_cannot_see_future(db, arena):
    competitor = add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"])
    _decision(db, competitor, T0, T0)
    with pytest.raises(psycopg.errors.CheckViolation):
        _decision(db, competitor, T0, T0 + timedelta(microseconds=1))


def test_masked_symbol_unique_per_competition(db, arena):
    a, b = make_asset(db), make_asset(db)
    sql = "INSERT INTO competition_asset (competition_id, asset_id, masked_symbol) VALUES (%s, %s, 'TKR_01')"
    db.execute(sql, (arena["competition"], a))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, (arena["competition"], b))


def test_second_agent_same_owner_rejected(db, arena):
    add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"])
    second = make_agent(db, arena["owner"], arena["model"], arena["credential"])
    with pytest.raises(psycopg.errors.RaiseException, match="one_agent_per_user"):
        add_competitor(db, arena["competition"], arena["session"], agent_id=second)


def test_agent_credential_must_belong_to_owner(db, arena):
    stranger = make_user(db)
    with pytest.raises(psycopg.errors.RaiseException, match="credential_not_owned"):
        make_agent(db, stranger, arena["model"], arena["credential"])


def test_agent_credential_provider_must_match_model(db, arena):
    openai_model = make_model(db, provider="OpenAI")
    with pytest.raises(psycopg.errors.RaiseException, match="credential_provider_mismatch"):
        make_agent(db, arena["owner"], openai_model, arena["credential"])


def test_contaminated_flag_set_when_cutoff_after_start(db, arena):
    add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"])
    flag = lambda: db.execute("SELECT contaminated FROM competition WHERE id = %s",
                              (arena["competition"],)).fetchone()["contaminated"]
    assert flag() is False
    other = make_user(db)
    late_model = make_model(db, cutoff="2025-01-01")
    late_agent = make_agent(db, other, late_model, make_credential(db, other))
    add_competitor(db, arena["competition"], arena["session"], agent_id=late_agent)
    assert flag() is True


def test_human_competitor_requires_user_portfolio(db, arena):
    with pytest.raises(psycopg.errors.RaiseException, match="competitor_owner_invalid"):
        with db.transaction():
            add_competitor(db, arena["competition"], arena["session"], agent_id=None, user_id=None)
    add_competitor(db, arena["competition"], arena["session"], agent_id=None, user_id=arena["owner"])


def test_agent_portfolio_must_not_have_user(db, arena):
    with pytest.raises(psycopg.errors.RaiseException, match="competitor_owner_invalid"):
        add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"],
                       user_id=arena["owner"])


def test_agent_model_locked_while_competing(db, arena):
    add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"])
    other_model = make_model(db, cutoff="2026-01-01")
    with pytest.raises(psycopg.errors.RaiseException, match="agent_locked_in_competition"):
        db.execute("UPDATE agent SET model_id = %s WHERE id = %s", (other_model, arena["agent"]))


def test_order_decision_must_belong_to_same_portfolio(db, arena):
    from tests.factories import make_order, make_portfolio
    competitor = add_competitor(db, arena["competition"], arena["session"], agent_id=arena["agent"])
    decision = _decision(db, competitor, T0, T0)
    foreign_portfolio = make_portfolio(db, arena["session"], arena["owner"])
    order = make_order(db, foreign_portfolio, make_asset(db), "buy", 1, T0)
    with pytest.raises(psycopg.errors.RaiseException, match="decision_portfolio_mismatch"):
        db.execute("UPDATE trade_order SET decision_id = %s WHERE id = %s", (decision, order))


def test_review_fills_must_belong_to_portfolio_and_asset(db, arena):
    from tests.factories import buy, make_portfolio, sell
    mine = make_portfolio(db, arena["session"], arena["owner"])
    other_user = make_user(db)
    theirs = make_portfolio(db, arena["session"], other_user)
    asset = make_asset(db)
    open_order = buy(db, mine, asset, 1, "10", T0)
    foreign_order = buy(db, theirs, asset, 1, "10", T0)
    fill_of = lambda o: db.execute("SELECT id FROM fill WHERE order_id = %s", (o,)).fetchone()["id"]
    sql = ("INSERT INTO trade_review (portfolio_id, asset_id, open_fill_id, close_fill_id, review_type, pnl, body) "
           "VALUES (%s, %s, %s, %s, 'rule', 0, 'x')")
    with pytest.raises(psycopg.errors.RaiseException, match="review_fill_mismatch"):
        db.execute(sql, (mine, asset, fill_of(open_order), fill_of(foreign_order)))
