-- =====================================================================
-- FMES Scanner — Supabase schema
-- Run this once in your Supabase project's SQL Editor.
-- =====================================================================

-- One row per scan run
CREATE TABLE IF NOT EXISTS scans (
    id              BIGSERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    universe_size   INT NOT NULL,
    setups_found    INT NOT NULL,
    failed_count    INT NOT NULL DEFAULT 0,
    timeframe       TEXT NOT NULL,
    universes       TEXT[] NOT NULL DEFAULT '{}',
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_scans_run_at ON scans(run_at DESC);

-- One row per detected setup signal
CREATE TABLE IF NOT EXISTS setups (
    id              BIGSERIAL PRIMARY KEY,
    scan_id         BIGINT REFERENCES scans(id) ON DELETE SET NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    signal_date     TIMESTAMPTZ NOT NULL,
    signal_bar      INT NOT NULL,
    bar_age         INT NOT NULL,
    entry           NUMERIC NOT NULL,
    sl              NUMERIC NOT NULL,
    tp              NUMERIC NOT NULL,
    tp1             NUMERIC,
    ob_entry        NUMERIC,
    ob_tp           NUMERIC,
    current_price   NUMERIC,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'live', 'won', 'lost')),
    premium         BOOLEAN NOT NULL DEFAULT FALSE,
    htf_trend       TEXT,
    has_lq_plus     BOOLEAN,
    risk_pct        NUMERIC,
    reward_pct      NUMERIC,
    rr              NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Unique key: same symbol + signal_date + direction = same setup (dedupe across scans)
    UNIQUE (symbol, direction, signal_date)
);

CREATE INDEX IF NOT EXISTS idx_setups_signal_date ON setups(signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_setups_symbol ON setups(symbol);
CREATE INDEX IF NOT EXISTS idx_setups_status ON setups(status);
CREATE INDEX IF NOT EXISTS idx_setups_premium ON setups(premium) WHERE premium = TRUE;
CREATE INDEX IF NOT EXISTS idx_setups_direction ON setups(direction);

-- Auto-update `updated_at` when a row changes
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_setups_updated_at ON setups;
CREATE TRIGGER trg_setups_updated_at
    BEFORE UPDATE ON setups
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- Views for the dashboard
-- =====================================================================

-- Latest snapshot per (symbol, direction, signal_date) — used by dashboard
CREATE OR REPLACE VIEW v_active_setups AS
SELECT *
FROM setups
WHERE status IN ('pending', 'live')
ORDER BY premium DESC, bar_age ASC, signal_date DESC;

-- Win rate aggregates over different time windows
CREATE OR REPLACE VIEW v_win_rate_30d AS
SELECT
    COUNT(*) FILTER (WHERE status = 'won') AS wins,
    COUNT(*) FILTER (WHERE status = 'lost') AS losses,
    COUNT(*) FILTER (WHERE status IN ('won', 'lost')) AS total_closed,
    CASE
        WHEN COUNT(*) FILTER (WHERE status IN ('won', 'lost')) = 0 THEN NULL
        ELSE ROUND(
            100.0 * COUNT(*) FILTER (WHERE status = 'won') /
            COUNT(*) FILTER (WHERE status IN ('won', 'lost')),
            1
        )
    END AS win_rate_pct,
    -- Expected-value calc (assumes 1R risk, 2.45R reward)
    CASE
        WHEN COUNT(*) FILTER (WHERE status IN ('won', 'lost')) = 0 THEN NULL
        ELSE ROUND(
            (COUNT(*) FILTER (WHERE status = 'won')::NUMERIC * 2.45 -
             COUNT(*) FILTER (WHERE status = 'lost')::NUMERIC * 1.0) /
            COUNT(*) FILTER (WHERE status IN ('won', 'lost')),
            2
        )
    END AS expectancy_r
FROM setups
WHERE signal_date >= NOW() - INTERVAL '30 days';

-- Per-symbol win rate (top performers)
CREATE OR REPLACE VIEW v_symbol_performance AS
SELECT
    symbol,
    COUNT(*) AS total_signals,
    COUNT(*) FILTER (WHERE status = 'won') AS wins,
    COUNT(*) FILTER (WHERE status = 'lost') AS losses,
    COUNT(*) FILTER (WHERE status IN ('pending', 'live')) AS open,
    CASE
        WHEN COUNT(*) FILTER (WHERE status IN ('won', 'lost')) = 0 THEN NULL
        ELSE ROUND(
            100.0 * COUNT(*) FILTER (WHERE status = 'won') /
            COUNT(*) FILTER (WHERE status IN ('won', 'lost')),
            1
        )
    END AS win_rate_pct
FROM setups
WHERE signal_date >= NOW() - INTERVAL '90 days'
GROUP BY symbol
HAVING COUNT(*) FILTER (WHERE status IN ('won', 'lost')) > 0
ORDER BY win_rate_pct DESC NULLS LAST, total_signals DESC;

-- =====================================================================
-- Row-Level Security: allow public read, restricted write
-- =====================================================================

ALTER TABLE scans  ENABLE ROW LEVEL SECURITY;
ALTER TABLE setups ENABLE ROW LEVEL SECURITY;

-- Anonymous read access (for the public dashboard)
DROP POLICY IF EXISTS scans_public_read ON scans;
CREATE POLICY scans_public_read  ON scans  FOR SELECT USING (true);

DROP POLICY IF EXISTS setups_public_read ON setups;
CREATE POLICY setups_public_read ON setups FOR SELECT USING (true);

-- Writes only via service-role key (used by the Python scanner)
-- (No INSERT/UPDATE policies for anon role → service_role bypasses RLS)
