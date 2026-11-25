-- Simulation sessions, portfolios, orders and the immutable fill ledger.

CREATE TYPE session_mode AS ENUM ('live', 'replay');
CREATE TYPE session_status AS ENUM ('created', 'running', 'paused', 'finished');
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit');
CREATE TYPE order_status AS ENUM ('pending', 'filled', 'rejected', 'cancelled');

CREATE TABLE sim_session (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id      bigint         NOT NULL REFERENCES app_user (id),
    mode               session_mode   NOT NULL,
    bar_timeframe      bar_timeframe  NOT NULL,
    start_at           timestamptz    NOT NULL,
    end_at             timestamptz,
    -- The session clock. Every read made on behalf of the session is bounded by it.
    sim_time           timestamptz    NOT NULL,
    speed              numeric(10,2)  NOT NULL DEFAULT 1 CHECK (speed > 0),
    status             session_status NOT NULL DEFAULT 'created',
    initial_cash       numeric(14,2)  NOT NULL CHECK (initial_cash > 0),
    period_length_days integer        CHECK (period_length_days > 0),
    created_at         timestamptz    NOT NULL DEFAULT now(),
    CHECK (end_at IS NULL OR end_at > start_at),
    CHECK (mode <> 'replay' OR (end_at IS NOT NULL AND sim_time BETWEEN start_at AND end_at))
);

CREATE TABLE trading_period (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id bigint      NOT NULL REFERENCES sim_session (id) ON DELETE CASCADE,
    period_no  integer     NOT NULL CHECK (period_no > 0),
    starts_at  timestamptz NOT NULL,
    ends_at    timestamptz NOT NULL,
    UNIQUE (session_id, period_no),
    CHECK (ends_at > starts_at)
);

CREATE INDEX trading_period_range_idx ON trading_period (session_id, starts_at, ends_at);

-- user_id is set for a human portfolio; an agent portfolio has NULL and is linked through competitor.
-- cash is a deliberate denormalization of the fill ledger, kept current by trg_fill_apply so
-- balance and limit checks stay O(1) and race-free under a row lock.
CREATE TABLE portfolio (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id bigint        NOT NULL REFERENCES sim_session (id) ON DELETE CASCADE,
    user_id    bigint        REFERENCES app_user (id),
    cash       numeric(14,2) NOT NULL CHECK (cash >= 0),
    created_at timestamptz   NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX portfolio_one_per_user_session ON portfolio (session_id, user_id)
    WHERE user_id IS NOT NULL;

CREATE FUNCTION portfolio_default_cash() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.cash IS NULL THEN
        SELECT initial_cash INTO NEW.cash FROM sim_session WHERE id = NEW.session_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_portfolio_default_cash
    BEFORE INSERT ON portfolio
    FOR EACH ROW EXECUTE FUNCTION portfolio_default_cash();

CREATE TABLE period_limit (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portfolio_id    bigint        NOT NULL REFERENCES portfolio (id) ON DELETE CASCADE,
    period_id       bigint        NOT NULL REFERENCES trading_period (id) ON DELETE CASCADE,
    max_buy_amount  numeric(14,2) CHECK (max_buy_amount >= 0),
    max_sell_amount numeric(14,2) CHECK (max_sell_amount >= 0),
    max_orders      integer       CHECK (max_orders >= 0),
    set_at          timestamptz   NOT NULL DEFAULT now(),
    UNIQUE (portfolio_id, period_id)
);

CREATE TABLE trade_order (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portfolio_id  bigint        NOT NULL REFERENCES portfolio (id) ON DELETE CASCADE,
    asset_id      bigint        NOT NULL REFERENCES asset (id),
    side          order_side    NOT NULL,
    order_type    order_type    NOT NULL DEFAULT 'market',
    quantity      numeric(14,4) NOT NULL CHECK (quantity > 0),
    limit_price   numeric(14,4) CHECK (limit_price > 0),
    placed_at_sim timestamptz   NOT NULL,
    status        order_status  NOT NULL DEFAULT 'pending',
    reject_reason text,
    decision_id   bigint,
    CHECK ((order_type = 'limit') = (limit_price IS NOT NULL)),
    CHECK ((status = 'rejected') = (reject_reason IS NOT NULL))
);

CREATE INDEX trade_order_portfolio_idx ON trade_order (portfolio_id, placed_at_sim);
CREATE INDEX trade_order_pending_idx ON trade_order (portfolio_id) WHERE status = 'pending';

-- Append-only ledger. Positions and realized results are derived from it.
CREATE TABLE fill (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id      bigint        NOT NULL UNIQUE REFERENCES trade_order (id),
    filled_at_sim timestamptz   NOT NULL,
    price         numeric(14,4) NOT NULL CHECK (price > 0),
    quantity      numeric(14,4) NOT NULL CHECK (quantity > 0),
    fee           numeric(14,2) NOT NULL DEFAULT 0 CHECK (fee >= 0)
);

-- Average cost uses all buys of the asset in the portfolio (average-cost method without reset).
CREATE VIEW position AS
SELECT o.portfolio_id,
       o.asset_id,
       sum(CASE WHEN o.side = 'buy' THEN f.quantity ELSE -f.quantity END) AS net_qty,
       round(sum(CASE WHEN o.side = 'buy' THEN f.price * f.quantity END)
             / nullif(sum(CASE WHEN o.side = 'buy' THEN f.quantity END), 0), 4) AS avg_cost
FROM fill f
JOIN trade_order o ON o.id = f.order_id
GROUP BY o.portfolio_id, o.asset_id
HAVING sum(CASE WHEN o.side = 'buy' THEN f.quantity ELSE -f.quantity END) > 0;

-- Period that contains a given instant for a portfolio's session.
CREATE FUNCTION period_limit_for(p_portfolio_id bigint, p_at timestamptz)
RETURNS period_limit
LANGUAGE sql STABLE AS $$
    SELECT pl.*
    FROM portfolio p
    JOIN trading_period tp ON tp.session_id = p.session_id
                          AND p_at >= tp.starts_at AND p_at < tp.ends_at
    JOIN period_limit pl ON pl.period_id = tp.id AND pl.portfolio_id = p.id
    WHERE p.id = p_portfolio_id
$$;

CREATE FUNCTION order_limit_count() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    lim        period_limit;
    period     trading_period;
    clock      timestamptz;
    sess_id    bigint;
    used       integer;
BEGIN
    -- Serialize order placement per portfolio so concurrent inserts cannot both pass the count.
    SELECT p.session_id INTO sess_id FROM portfolio p WHERE p.id = NEW.portfolio_id FOR UPDATE;
    SELECT sim_time INTO clock FROM sim_session WHERE id = sess_id;

    -- Orders are stamped with the session clock; back- or forward-dating would dodge period limits.
    IF NEW.placed_at_sim <> clock THEN
        RAISE EXCEPTION 'order_time_mismatch' USING ERRCODE = 'P0001';
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

CREATE TRIGGER trg_order_limit_count
    BEFORE INSERT ON trade_order
    FOR EACH ROW EXECUTE FUNCTION order_limit_count();

CREATE FUNCTION fill_apply() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    ord      trade_order;
    lim      period_limit;
    period   trading_period;
    held     numeric;
    used     numeric;
    clock    timestamptz;
    notional numeric;
BEGIN
    SELECT * INTO ord FROM trade_order WHERE id = NEW.order_id;

    -- Row lock on the portfolio serializes all fills of one portfolio.
    PERFORM 1 FROM portfolio WHERE id = ord.portfolio_id FOR UPDATE;

    SELECT s.sim_time INTO clock
    FROM portfolio p JOIN sim_session s ON s.id = p.session_id
    WHERE p.id = ord.portfolio_id;
    IF NEW.filled_at_sim < ord.placed_at_sim OR NEW.filled_at_sim > clock THEN
        RAISE EXCEPTION 'fill_time_invalid' USING ERRCODE = 'P0001';
    END IF;

    -- Cash is kept in cents: round buys up and sells down so tiny trades are never free.
    notional := CASE WHEN ord.side = 'buy' THEN ceil(NEW.price * NEW.quantity * 100) / 100
                     ELSE floor(NEW.price * NEW.quantity * 100) / 100 END;

    IF ord.status <> 'pending' THEN
        RAISE EXCEPTION 'order_not_pending' USING ERRCODE = 'P0001';
    END IF;
    IF NEW.quantity <> ord.quantity THEN
        RAISE EXCEPTION 'fill_quantity_mismatch' USING ERRCODE = 'P0001';
    END IF;

    IF ord.side = 'sell' THEN
        SELECT coalesce(sum(net_qty), 0) INTO held
        FROM position WHERE portfolio_id = ord.portfolio_id AND asset_id = ord.asset_id;
        IF held < NEW.quantity THEN
            RAISE EXCEPTION 'insufficient_position' USING ERRCODE = 'P0001';
        END IF;
    END IF;

    -- Amount limits count against the period in which the order was placed.
    lim := period_limit_for(ord.portfolio_id, ord.placed_at_sim);
    IF lim.id IS NOT NULL THEN
        SELECT * INTO period FROM trading_period WHERE id = lim.period_id;
        SELECT coalesce(sum(f.price * f.quantity), 0) INTO used
        FROM fill f
        JOIN trade_order o ON o.id = f.order_id
        WHERE o.portfolio_id = ord.portfolio_id
          AND o.side = ord.side
          AND o.placed_at_sim >= period.starts_at AND o.placed_at_sim < period.ends_at;

        IF (ord.side = 'buy' AND lim.max_buy_amount IS NOT NULL AND used + notional > lim.max_buy_amount)
           OR (ord.side = 'sell' AND lim.max_sell_amount IS NOT NULL AND used + notional > lim.max_sell_amount) THEN
            RAISE EXCEPTION 'period_limit_exceeded' USING ERRCODE = 'P0001', DETAIL = ord.side || '_amount';
        END IF;
    END IF;

    UPDATE portfolio
    SET cash = cash + CASE WHEN ord.side = 'buy' THEN -(notional + NEW.fee) ELSE notional - NEW.fee END
    WHERE id = ord.portfolio_id;

    UPDATE trade_order SET status = 'filled' WHERE id = ord.id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_fill_apply
    BEFORE INSERT ON fill
    FOR EACH ROW EXECUTE FUNCTION fill_apply();

CREATE FUNCTION fill_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'fill_is_immutable' USING ERRCODE = 'P0001';
END;
$$;

CREATE TRIGGER trg_fill_immutable
    BEFORE UPDATE OR DELETE ON fill
    FOR EACH ROW EXECUTE FUNCTION fill_immutable();
