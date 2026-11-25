-- Users, LLM catalog and the tradable asset universe.

CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE app_user (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         citext      NOT NULL UNIQUE,
    password_hash text        NOT NULL,
    display_name  text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE llm_provider (
    id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE llm_model (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_id      bigint NOT NULL REFERENCES llm_provider (id),
    model_code       text   NOT NULL,
    knowledge_cutoff date   NOT NULL,
    UNIQUE (provider_id, model_code)
);

-- API keys are encrypted by the application; only the last 4 chars are stored in clear.
CREATE TABLE user_api_credential (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       bigint      NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    provider_id   bigint      NOT NULL REFERENCES llm_provider (id),
    encrypted_key bytea       NOT NULL,
    key_last4     char(4)     NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider_id)
);

CREATE TABLE sector (
    id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE exchange (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code     text NOT NULL UNIQUE,
    name     text NOT NULL,
    timezone text NOT NULL
);

CREATE TABLE asset (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol      text    NOT NULL UNIQUE,
    name        text    NOT NULL,
    sector_id   bigint  NOT NULL REFERENCES sector (id),
    exchange_id bigint  NOT NULL REFERENCES exchange (id),
    is_active   boolean NOT NULL DEFAULT true
);

CREATE INDEX asset_sector_idx ON asset (sector_id);

INSERT INTO llm_provider (name) VALUES ('Anthropic'), ('OpenAI'), ('Google');

INSERT INTO exchange (code, name, timezone) VALUES
    ('NASDAQ', 'Nasdaq Stock Market', 'America/New_York'),
    ('NYSE', 'New York Stock Exchange', 'America/New_York');
