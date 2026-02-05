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

-- Phase 5C: Strategy run metadata
CREATE TABLE IF NOT EXISTS strategy_runs (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    broker_type VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    initial_capital DOUBLE PRECISION,
    final_capital DOUBLE PRECISION,
    total_trades INT DEFAULT 0,
    config JSONB
);

-- Add run_id to trades
ALTER TABLE trades ADD COLUMN IF NOT EXISTS run_id INT REFERENCES strategy_runs(id);

-- Phase 5C: Daily P&L summary
CREATE TABLE IF NOT EXISTS daily_summary (
    id SERIAL PRIMARY KEY,
    run_id INT REFERENCES strategy_runs(id),
    date DATE NOT NULL,
    realized_pnl DOUBLE PRECISION DEFAULT 0,
    trade_count INT DEFAULT 0,
    win_count INT DEFAULT 0,
    max_drawdown DOUBLE PRECISION DEFAULT 0,
    UNIQUE(run_id, date)
);
