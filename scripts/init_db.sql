CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS candles (
    timestamp   TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(20) NOT NULL,
    timeframe   VARCHAR(10) NOT NULL,
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION NOT NULL DEFAULT 0,
    spread      DOUBLE PRECISION,
    UNIQUE (timestamp, symbol, timeframe)
);

SELECT create_hypertable('candles', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts
    ON candles (symbol, timeframe, timestamp DESC);

CREATE TABLE IF NOT EXISTS ticks (
    timestamp   TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(20) NOT NULL,
    bid         DOUBLE PRECISION NOT NULL,
    ask         DOUBLE PRECISION NOT NULL
);

SELECT create_hypertable('ticks', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts
    ON ticks (symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    strategy_name   VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    side            VARCHAR(4) NOT NULL,
    entry_time      TIMESTAMPTZ NOT NULL,
    exit_time       TIMESTAMPTZ,
    entry_price     DOUBLE PRECISION NOT NULL,
    exit_price      DOUBLE PRECISION,
    volume          DOUBLE PRECISION NOT NULL,
    pnl             DOUBLE PRECISION,
    sl              DOUBLE PRECISION,
    tp              DOUBLE PRECISION,
    exit_reason     VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_strategy_symbol
    ON trades (strategy_name, symbol);
