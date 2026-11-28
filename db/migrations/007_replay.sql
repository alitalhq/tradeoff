-- Replay engine: per-session asset universe, corporate action ledger, order guards.

-- Assets a session trades. No rows means the session is unrestricted.
CREATE TABLE session_asset (
    session_id bigint NOT NULL REFERENCES sim_session (id) ON DELETE CASCADE,
    asset_id   bigint NOT NULL REFERENCES asset (id),
    PRIMARY KEY (session_id, asset_id)
);

-- Append-only record of a split or dividend applied to one portfolio. Fills stay untouched:
-- a split changes held quantity through qty_delta (negative for a reverse split), a dividend
-- credits cash_delta. One row per (portfolio, action) makes applying idempotent.
CREATE TABLE corporate_action_applied (
    portfolio_id        bigint        NOT NULL REFERENCES portfolio (id) ON DELETE CASCADE,
    corporate_action_id bigint        NOT NULL REFERENCES corporate_action (id),
    applied_at_sim      timestamptz   NOT NULL,
    qty_delta           numeric(14,4) NOT NULL DEFAULT 0,
    cash_delta          numeric(14,2) NOT NULL DEFAULT 0 CHECK (cash_delta >= 0),
    PRIMARY KEY (portfolio_id, corporate_action_id)
);

CREATE FUNCTION corporate_action_applied_apply() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    clock timestamptz;
BEGIN
    PERFORM 1 FROM portfolio WHERE id = NEW.portfolio_id FOR UPDATE;
    SELECT s.sim_time INTO clock
    FROM portfolio p JOIN sim_session s ON s.id = p.session_id
    WHERE p.id = NEW.portfolio_id;
    IF NEW.applied_at_sim > clock THEN
        RAISE EXCEPTION 'adjustment_time_invalid' USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_corporate_action_applied_apply
    BEFORE INSERT ON corporate_action_applied
    FOR EACH ROW EXECUTE FUNCTION corporate_action_applied_apply();

-- AFTER, so a row skipped by ON CONFLICT DO NOTHING never credits cash.
CREATE FUNCTION corporate_action_applied_credit() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.cash_delta <> 0 THEN
        UPDATE portfolio SET cash = cash + NEW.cash_delta WHERE id = NEW.portfolio_id;
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_corporate_action_applied_credit
    AFTER INSERT ON corporate_action_applied
    FOR EACH ROW EXECUTE FUNCTION corporate_action_applied_credit();

CREATE FUNCTION corporate_action_applied_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'adjustment_is_immutable' USING ERRCODE = 'P0001';
END;
$$;

CREATE TRIGGER trg_corporate_action_applied_immutable
    BEFORE UPDATE OR DELETE ON corporate_action_applied
    FOR EACH ROW EXECUTE FUNCTION corporate_action_applied_immutable();

-- Quantity = signed fills + split adjustments. Average cost divides buy cost by buy quantity,
-- each buy scaled by the splits applied after it, so earlier sells do not distort it.
CREATE OR REPLACE VIEW position AS
WITH ledger AS (
    SELECT o.portfolio_id, o.asset_id,
           CASE WHEN o.side = 'buy' THEN f.quantity ELSE -f.quantity END AS qty,
           CASE WHEN o.side = 'buy' THEN f.price * f.quantity END AS buy_cost,
           CASE WHEN o.side = 'buy' THEN f.quantity * coalesce((
               SELECT exp(sum(ln(ca.ratio)))
               FROM corporate_action_applied ap
               JOIN corporate_action ca ON ca.id = ap.corporate_action_id
               WHERE ap.portfolio_id = o.portfolio_id
                 AND ca.asset_id = o.asset_id
                 AND ca.action_type = 'split'
                 AND ca.effective_at > f.filled_at_sim
           ), 1) END AS buy_qty_adjusted
    FROM fill f
    JOIN trade_order o ON o.id = f.order_id
    UNION ALL
    SELECT ap.portfolio_id, ca.asset_id, ap.qty_delta, NULL, NULL
    FROM corporate_action_applied ap
    JOIN corporate_action ca ON ca.id = ap.corporate_action_id
    WHERE ca.action_type = 'split'
)
SELECT portfolio_id,
       asset_id,
       sum(qty) AS net_qty,
       round(sum(buy_cost) / nullif(sum(buy_qty_adjusted), 0), 4) AS avg_cost
FROM ledger
GROUP BY portfolio_id, asset_id
HAVING sum(qty) > 0;

-- Apply every split/dividend effective in (p_from, p_to] to each portfolio of the session holding it.
CREATE FUNCTION apply_corporate_actions(p_session_id bigint, p_from timestamptz, p_to timestamptz)
RETURNS SETOF corporate_action_applied
LANGUAGE plpgsql AS $$
DECLARE
    act corporate_action;
BEGIN
    FOR act IN
        SELECT ca.* FROM corporate_action ca
        WHERE ca.effective_at > p_from AND ca.effective_at <= p_to
          AND (NOT EXISTS (SELECT 1 FROM session_asset WHERE session_id = p_session_id)
               OR EXISTS (SELECT 1 FROM session_asset
                          WHERE session_id = p_session_id AND asset_id = ca.asset_id))
        ORDER BY ca.effective_at, ca.id
    LOOP
        RETURN QUERY
        INSERT INTO corporate_action_applied (portfolio_id, corporate_action_id, applied_at_sim,
                                              qty_delta, cash_delta)
        SELECT pos.portfolio_id, act.id, act.effective_at,
               CASE WHEN act.action_type = 'split' THEN round(pos.net_qty * (act.ratio - 1), 4) ELSE 0 END,
               CASE WHEN act.action_type = 'dividend' THEN floor(pos.net_qty * act.amount * 100) / 100 ELSE 0 END
        FROM position pos
        JOIN portfolio p ON p.id = pos.portfolio_id
        WHERE p.session_id = p_session_id AND pos.asset_id = act.asset_id
        ORDER BY pos.portfolio_id
        ON CONFLICT (portfolio_id, corporate_action_id) DO NOTHING
        RETURNING *;
    END LOOP;
END;
$$;

-- Order placement guards, now also refusing finished sessions and assets outside the universe.
CREATE OR REPLACE FUNCTION order_limit_count() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    lim        period_limit;
    period     trading_period;
    sess       sim_session;
    sess_id    bigint;
    used       integer;
BEGIN
    -- Serialize order placement per portfolio so concurrent inserts cannot both pass the count.
    SELECT p.session_id INTO sess_id FROM portfolio p WHERE p.id = NEW.portfolio_id FOR UPDATE;
    SELECT * INTO sess FROM sim_session WHERE id = sess_id;

    IF sess.status = 'finished' THEN
        RAISE EXCEPTION 'session_finished' USING ERRCODE = 'P0001';
    END IF;

    -- Orders are stamped with the session clock; back- or forward-dating would dodge period limits.
    IF NEW.placed_at_sim <> sess.sim_time THEN
        RAISE EXCEPTION 'order_time_mismatch' USING ERRCODE = 'P0001';
    END IF;

    IF EXISTS (SELECT 1 FROM session_asset WHERE session_id = sess_id)
       AND NOT EXISTS (SELECT 1 FROM session_asset WHERE session_id = sess_id AND asset_id = NEW.asset_id) THEN
        RAISE EXCEPTION 'asset_not_in_session' USING ERRCODE = 'P0001';
    END IF;

    -- Fail closed: once a session has trading periods, every order must fall inside one.
    IF EXISTS (SELECT 1 FROM trading_period WHERE session_id = sess_id)
       AND NOT EXISTS (SELECT 1 FROM trading_period
                       WHERE session_id = sess_id
                         AND NEW.placed_at_sim >= starts_at AND NEW.placed_at_sim < ends_at) THEN
        RAISE EXCEPTION 'no_trading_period' USING ERRCODE = 'P0001';
    END IF;

    lim := period_limit_for(NEW.portfolio_id, NEW.placed_at_sim);
    IF lim.id IS NULL OR lim.max_orders IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT * INTO period FROM trading_period WHERE id = lim.period_id;

    SELECT count(*) INTO used
    FROM trade_order
    WHERE portfolio_id = NEW.portfolio_id
      AND status <> 'rejected'
      AND placed_at_sim >= period.starts_at AND placed_at_sim < period.ends_at;

    IF used >= lim.max_orders THEN
        RAISE EXCEPTION 'period_limit_exceeded' USING ERRCODE = 'P0001', DETAIL = 'max_orders';
    END IF;
    RETURN NEW;
END;
$$;
