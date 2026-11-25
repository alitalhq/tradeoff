-- Price bars, corporate actions and news.

CREATE TYPE bar_timeframe AS ENUM ('1m', '1h', '1d');

CREATE TABLE price_bar (
    asset_id  bigint        NOT NULL REFERENCES asset (id),
    timeframe bar_timeframe NOT NULL,
    bar_start timestamptz   NOT NULL,
    -- A bar becomes visible to a session only once bar_end <= sim_time.
    bar_end   timestamptz   NOT NULL,
    open      numeric(14,4) NOT NULL,
    high      numeric(14,4) NOT NULL,
    low       numeric(14,4) NOT NULL,
    close     numeric(14,4) NOT NULL,
    volume    bigint        NOT NULL,
    PRIMARY KEY (asset_id, timeframe, bar_start),
    CHECK (bar_end > bar_start),
    CHECK (low > 0),
    CHECK (low <= least(open, close)),
    CHECK (high >= greatest(open, close)),
    CHECK (volume >= 0)
) PARTITION BY RANGE (bar_start);

CREATE TABLE price_bar_2016 PARTITION OF price_bar FOR VALUES FROM ('2016-01-01 00:00+00') TO ('2017-01-01 00:00+00');
CREATE TABLE price_bar_2017 PARTITION OF price_bar FOR VALUES FROM ('2017-01-01 00:00+00') TO ('2018-01-01 00:00+00');
CREATE TABLE price_bar_2018 PARTITION OF price_bar FOR VALUES FROM ('2018-01-01 00:00+00') TO ('2019-01-01 00:00+00');
CREATE TABLE price_bar_2019 PARTITION OF price_bar FOR VALUES FROM ('2019-01-01 00:00+00') TO ('2020-01-01 00:00+00');
CREATE TABLE price_bar_2020 PARTITION OF price_bar FOR VALUES FROM ('2020-01-01 00:00+00') TO ('2021-01-01 00:00+00');
CREATE TABLE price_bar_2021 PARTITION OF price_bar FOR VALUES FROM ('2021-01-01 00:00+00') TO ('2022-01-01 00:00+00');
CREATE TABLE price_bar_2022 PARTITION OF price_bar FOR VALUES FROM ('2022-01-01 00:00+00') TO ('2023-01-01 00:00+00');
CREATE TABLE price_bar_2023 PARTITION OF price_bar FOR VALUES FROM ('2023-01-01 00:00+00') TO ('2024-01-01 00:00+00');
CREATE TABLE price_bar_2024 PARTITION OF price_bar FOR VALUES FROM ('2024-01-01 00:00+00') TO ('2025-01-01 00:00+00');
CREATE TABLE price_bar_2025 PARTITION OF price_bar FOR VALUES FROM ('2025-01-01 00:00+00') TO ('2026-01-01 00:00+00');
CREATE TABLE price_bar_2026 PARTITION OF price_bar FOR VALUES FROM ('2026-01-01 00:00+00') TO ('2027-01-01 00:00+00');
CREATE TABLE price_bar_2027 PARTITION OF price_bar FOR VALUES FROM ('2027-01-01 00:00+00') TO ('2028-01-01 00:00+00');
CREATE TABLE price_bar_default PARTITION OF price_bar DEFAULT;

CREATE INDEX price_bar_visibility_idx ON price_bar (asset_id, timeframe, bar_end);

CREATE TYPE corporate_action_type AS ENUM ('split', 'dividend');

CREATE TABLE corporate_action (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id     bigint                NOT NULL REFERENCES asset (id),
    action_type  corporate_action_type NOT NULL,
    effective_at timestamptz           NOT NULL,
    ratio        numeric(12,6),
    amount       numeric(14,4),
    CHECK (
        (action_type = 'split' AND ratio IS NOT NULL AND ratio > 0 AND amount IS NULL)
        OR (action_type = 'dividend' AND amount IS NOT NULL AND amount > 0 AND ratio IS NULL)
    )
);

CREATE INDEX corporate_action_asset_idx ON corporate_action (asset_id, effective_at);

CREATE TABLE news (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source       text        NOT NULL,
    external_id  text        NOT NULL,
    headline     text        NOT NULL,
    summary      text        NOT NULL DEFAULT '',
    url          text        NOT NULL,
    -- First publication time (never the revision time) so revisions cannot leak the future.
    published_at timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE INDEX news_published_idx ON news (published_at);

CREATE TABLE news_asset (
    news_id  bigint NOT NULL REFERENCES news (id) ON DELETE CASCADE,
    asset_id bigint NOT NULL REFERENCES asset (id),
    PRIMARY KEY (news_id, asset_id)
);

CREATE INDEX news_asset_asset_idx ON news_asset (asset_id, news_id);
