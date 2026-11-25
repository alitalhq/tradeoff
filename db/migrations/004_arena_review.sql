-- AI arena (agents, competitions, decisions, lessons) and trade reviews.

CREATE TABLE agent (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id   bigint      NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    name            text        NOT NULL,
    model_id        bigint      NOT NULL REFERENCES llm_model (id),
    credential_id   bigint      NOT NULL REFERENCES user_api_credential (id),
    strategy_prompt text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_user_id, name)
);

CREATE FUNCTION agent_credential_check() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    cred user_api_credential;
    model_provider bigint;
BEGIN
    SELECT * INTO cred FROM user_api_credential WHERE id = NEW.credential_id;
    IF cred.user_id <> NEW.owner_user_id THEN
        RAISE EXCEPTION 'credential_not_owned' USING ERRCODE = 'P0001';
    END IF;
    SELECT provider_id INTO model_provider FROM llm_model WHERE id = NEW.model_id;
    IF cred.provider_id <> model_provider THEN
        RAISE EXCEPTION 'credential_provider_mismatch' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_agent_credential_check
    BEFORE INSERT OR UPDATE OF owner_user_id, model_id, credential_id ON agent
    FOR EACH ROW EXECUTE FUNCTION agent_credential_check();

CREATE TABLE competition (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_by        bigint      NOT NULL REFERENCES app_user (id),
    session_id        bigint      NOT NULL UNIQUE REFERENCES sim_session (id) ON DELETE CASCADE,
    -- Mask tickers, company names and absolute dates in agent prompts.
    anonymized        boolean     NOT NULL DEFAULT true,
    decision_interval interval    NOT NULL CHECK (decision_interval > interval '0'),
    -- True when any competing model's knowledge cutoff is on/after the replay start.
    contaminated      boolean     NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- agent_id NULL means a human competitor whose portfolio has a user_id.
CREATE TABLE competitor (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    competition_id bigint NOT NULL REFERENCES competition (id) ON DELETE CASCADE,
    portfolio_id   bigint NOT NULL UNIQUE REFERENCES portfolio (id),
    agent_id       bigint REFERENCES agent (id),
    UNIQUE (competition_id, agent_id)
);

CREATE FUNCTION competitor_check() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    pf         portfolio;
    comp       competition;
    owner_id   bigint;
    cutoff     date;
    session_start timestamptz;
BEGIN
    -- Lock the competition so concurrent entries see each other (one_agent_per_user check below).
    SELECT * INTO comp FROM competition WHERE id = NEW.competition_id FOR UPDATE;
    SELECT * INTO pf FROM portfolio WHERE id = NEW.portfolio_id;

    IF pf.session_id <> comp.session_id THEN
        RAISE EXCEPTION 'competitor_session_mismatch' USING ERRCODE = 'P0001';
    END IF;
    IF (NEW.agent_id IS NULL) = (pf.user_id IS NULL) THEN
        RAISE EXCEPTION 'competitor_owner_invalid' USING ERRCODE = 'P0001';
    END IF;

    IF NEW.agent_id IS NOT NULL THEN
        SELECT a.owner_user_id, m.knowledge_cutoff INTO owner_id, cutoff
        FROM agent a JOIN llm_model m ON m.id = a.model_id
        WHERE a.id = NEW.agent_id;

        -- One agent per owner per competition. Lives in a trigger because the BCNF
        -- decomposition (agent / competitor) removed the table where it was a key.
        IF EXISTS (
            SELECT 1 FROM competitor c JOIN agent a ON a.id = c.agent_id
            WHERE c.competition_id = NEW.competition_id
              AND a.owner_user_id = owner_id
              AND c.id IS DISTINCT FROM NEW.id
        ) THEN
            RAISE EXCEPTION 'one_agent_per_user' USING ERRCODE = 'P0001';
        END IF;

        SELECT start_at INTO session_start FROM sim_session WHERE id = comp.session_id;
        IF cutoff >= (session_start AT TIME ZONE 'UTC')::date THEN
            UPDATE competition SET contaminated = true WHERE id = comp.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_competitor_check
    BEFORE INSERT OR UPDATE ON competitor
    FOR EACH ROW EXECUTE FUNCTION competitor_check();

CREATE TABLE competition_asset (
    competition_id bigint NOT NULL REFERENCES competition (id) ON DELETE CASCADE,
    asset_id       bigint NOT NULL REFERENCES asset (id),
    masked_symbol  text   NOT NULL,
    PRIMARY KEY (competition_id, asset_id),
    UNIQUE (competition_id, masked_symbol)
);

-- Audit trail of every agent call. The CHECK is the stored proof that no decision saw the future.
CREATE TABLE agent_decision (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    competitor_id     bigint      NOT NULL REFERENCES competitor (id) ON DELETE CASCADE,
    sim_time          timestamptz NOT NULL,
    context_hash      bytea       NOT NULL,
    context_max_ts    timestamptz NOT NULL,
    prompt_tokens     integer     CHECK (prompt_tokens >= 0),
    completion_tokens integer     CHECK (completion_tokens >= 0),
    raw_response      jsonb,
    rationale         text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (context_max_ts <= sim_time)
);

-- sim_time is not self-reported: it must be the session clock at the moment of the decision.
CREATE FUNCTION decision_time_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.sim_time IS DISTINCT FROM (
        SELECT s.sim_time FROM competitor c
        JOIN portfolio p ON p.id = c.portfolio_id
        JOIN sim_session s ON s.id = p.session_id
        WHERE c.id = NEW.competitor_id
    ) THEN
        RAISE EXCEPTION 'decision_time_mismatch' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_decision_time_check
    BEFORE INSERT OR UPDATE ON agent_decision
    FOR EACH ROW EXECUTE FUNCTION decision_time_check();

CREATE INDEX agent_decision_competitor_idx ON agent_decision (competitor_id, sim_time);

ALTER TABLE trade_order
    ADD CONSTRAINT trade_order_decision_fk FOREIGN KEY (decision_id) REFERENCES agent_decision (id);

-- An order may only cite a decision made for its own portfolio.
CREATE FUNCTION order_decision_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.decision_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM agent_decision d JOIN competitor c ON c.id = d.competitor_id
        WHERE d.id = NEW.decision_id AND c.portfolio_id = NEW.portfolio_id
    ) THEN
        RAISE EXCEPTION 'decision_portfolio_mismatch' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_decision_check
    BEFORE INSERT OR UPDATE OF decision_id, portfolio_id ON trade_order
    FOR EACH ROW EXECUTE FUNCTION order_decision_check();

-- Model and owner are frozen once an agent has entered a competition, so the
-- one-agent-per-user rule and the contamination flag cannot be bypassed afterwards.
CREATE FUNCTION agent_lock_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.model_id <> OLD.model_id OR NEW.owner_user_id <> OLD.owner_user_id)
       AND EXISTS (SELECT 1 FROM competitor WHERE agent_id = OLD.id) THEN
        RAISE EXCEPTION 'agent_locked_in_competition' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_agent_lock_check
    BEFORE UPDATE OF model_id, owner_user_id ON agent
    FOR EACH ROW EXECUTE FUNCTION agent_lock_check();

CREATE TABLE agent_lesson (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_id           bigint      NOT NULL REFERENCES agent (id) ON DELETE CASCADE,
    source_decision_id bigint      REFERENCES agent_decision (id) ON DELETE SET NULL,
    lesson             text        NOT NULL,
    created_at_sim     timestamptz NOT NULL
);

CREATE INDEX agent_lesson_agent_idx ON agent_lesson (agent_id, created_at_sim);

CREATE TYPE review_type AS ENUM ('rule', 'llm');

CREATE TABLE trade_review (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portfolio_id  bigint        NOT NULL REFERENCES portfolio (id) ON DELETE CASCADE,
    asset_id      bigint        NOT NULL REFERENCES asset (id),
    open_fill_id  bigint        NOT NULL REFERENCES fill (id),
    close_fill_id bigint        NOT NULL REFERENCES fill (id),
    review_type   review_type   NOT NULL,
    pnl           numeric(14,2) NOT NULL,
    post_move_pct numeric(8,4),
    body          text          NOT NULL,
    created_at    timestamptz   NOT NULL DEFAULT now(),
    CHECK (open_fill_id <> close_fill_id)
);

-- Both fills must come from orders of the reviewed portfolio and asset.
CREATE FUNCTION trade_review_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT count(*) FROM fill f JOIN trade_order o ON o.id = f.order_id
        WHERE f.id IN (NEW.open_fill_id, NEW.close_fill_id)
          AND o.portfolio_id = NEW.portfolio_id
          AND o.asset_id = NEW.asset_id) <> 2 THEN
        RAISE EXCEPTION 'review_fill_mismatch' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_trade_review_check
    BEFORE INSERT OR UPDATE ON trade_review
    FOR EACH ROW EXECUTE FUNCTION trade_review_check();

CREATE TABLE trade_review_news (
    review_id bigint NOT NULL REFERENCES trade_review (id) ON DELETE CASCADE,
    news_id   bigint NOT NULL REFERENCES news (id),
    PRIMARY KEY (review_id, news_id)
);
