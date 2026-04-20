-- Symbols on the watchlist
CREATE TABLE IF NOT EXISTS symbols (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    sector VARCHAR(50),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Every signal fired by the Signal Detector
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,   -- volume_surge | rsi_oversold | breakout | etc.
    value FLOAT,                         -- numeric value that triggered the signal
    price FLOAT NOT NULL,
    context JSONB,                       -- rsi, vwap, volume etc at time of signal
    fired_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Full trade records with provenance
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(5) NOT NULL,       -- LONG | SHORT
    status VARCHAR(20) DEFAULT 'OPEN',   -- OPEN | CLOSED | CANCELLED

    -- Entry
    entry_price FLOAT,
    size_pct FLOAT,                      -- % of portfolio
    quantity FLOAT,
    entry_order_id VARCHAR(100),
    opened_at TIMESTAMPTZ,

    -- Exit
    exit_price FLOAT,
    exit_order_id VARCHAR(100),
    closed_at TIMESTAMPTZ,
    pnl_pct FLOAT,
    pnl_usd FLOAT,
    exit_reason VARCHAR(50),             -- stop_loss | take_profit | agent_exit | manual

    -- Agent reasoning (provenance)
    signal_id INT REFERENCES signals(id),
    thesis TEXT,
    investigation_steps JSONB,           -- full ReAct loop trace
    evidence_refs JSONB,                 -- tool call results that drove decision
    confidence FLOAT,
    strategy_call_id VARCHAR(100),
    model_version VARCHAR(50),

    -- Risk check
    risk_check_result VARCHAR(20),       -- APPROVED | BLOCKED
    risk_check_reason TEXT,

    -- Targets set at entry
    stop_price FLOAT,
    target_price FLOAT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Per-symbol, per-signal-type performance stats (learning loop)
CREATE TABLE IF NOT EXISTS signal_stats (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    avg_pnl_pct FLOAT DEFAULT 0.0,
    avg_hold_minutes FLOAT DEFAULT 0.0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, signal_type)
);

-- Portfolio snapshots (point-in-time state)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    cash FLOAT NOT NULL,
    total_value FLOAT NOT NULL,
    positions JSONB,
    daily_pnl_pct FLOAT,
    daily_pnl_usd FLOAT,
    snapshotted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_fired_at ON signals(fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_stats_lookup ON signal_stats(symbol, signal_type);
