-- ============================================================
-- kri_queries.sql
-- VPBank Young Talents 2026 — Topic 2
-- Early-warning KRI computations over synthetic operational logs.
--
-- Dialect: PostgreSQL / DuckDB compatible.
-- All input data is SYNTHETIC and ILLUSTRATIVE (see /data).
--
-- These queries run in the notebook via DuckDB, which reads the
-- CSV files in /data directly (read_csv_auto). In a production
-- warehouse the same SQL would run against governed tables.
-- ============================================================


-- ------------------------------------------------------------
-- KRI 1 — Transaction Failure Rate (SYSTEM + PARTNER only)
-- % of transactions failed due to SYSTEM or PARTNER errors.
-- CLIENT errors (wrong OTP, insufficient funds) are excluded:
-- they are customer behaviour, not an operational-risk signal.
-- ------------------------------------------------------------
SELECT
    date,
    total_tx,
    (fail_system + fail_partner)                             AS fail_syspartner,
    ROUND(100.0 * (fail_system + fail_partner)
          / NULLIF(total_tx, 0), 2)                          AS fail_rate_pct
FROM read_csv_auto('../data/transactions_daily.csv')
ORDER BY date;


-- ------------------------------------------------------------
-- KRI 2 — Failure Rate Velocity (Δ over the previous day)
-- Rate of change of KRI 1 vs the prior period. Catches
-- degradation that is still below the absolute limit but
-- accelerating. (Daily proxy for the 30-min window on the slide.)
-- ------------------------------------------------------------
WITH k1 AS (
    SELECT
        date,
        ROUND(100.0 * (fail_system + fail_partner)
              / NULLIF(total_tx, 0), 4)                      AS fail_rate_pct
    FROM read_csv_auto('../data/transactions_daily.csv')
)
SELECT
    date,
    fail_rate_pct,
    ROUND(fail_rate_pct
          / NULLIF(LAG(fail_rate_pct) OVER (ORDER BY date), 0), 2)
                                                             AS velocity_ratio
FROM k1
ORDER BY date;


-- ------------------------------------------------------------
-- KRI 3 — Users with >= 3 failed transactions (% of active users)
-- Measures customer-facing pain: how many users hit repeated
-- failures, not just the raw system failure rate.
-- NOTE (synthetic data): users_3plus_fails is generated with a
-- built-in correlation to injected outages, so on this dataset
-- KRI 3 is a transparent proxy rather than an independent signal.
-- ------------------------------------------------------------
SELECT
    date,
    ROUND(100.0 * users_3plus_fails
          / NULLIF(active_users, 0), 2)                      AS users_3fail_pct
FROM read_csv_auto('../data/transactions_daily.csv')
ORDER BY date;


-- ------------------------------------------------------------
-- KRI 4 — eKYC Step-level Drop-off
-- Drop-off rate at each onboarding step. Liveness is expected
-- to be the bottleneck. Computed as drop / started.
-- ------------------------------------------------------------
SELECT
    date,
    started,
    ROUND(100.0 * drop_document / NULLIF(started, 0), 2)     AS drop_document_pct,
    ROUND(100.0 * drop_liveness / NULLIF(started, 0), 2)     AS drop_liveness_pct,
    ROUND(100.0 * drop_matching / NULLIF(started, 0), 2)     AS drop_matching_pct,
    ROUND(100.0 * (started - completed) / NULLIF(started, 0), 2)
                                                             AS total_dropoff_pct
FROM read_csv_auto('../data/ekyc_daily.csv')
ORDER BY date;


-- ------------------------------------------------------------
-- KRI 5 — Manual Override Rate
-- Ratio of manual overrides to total transactions.
-- ------------------------------------------------------------
SELECT
    date,
    ROUND(100.0 * manual_override / NULLIF(total_tx, 0), 3)  AS override_rate_pct
FROM read_csv_auto('../data/transactions_daily.csv')
ORDER BY date;


-- ------------------------------------------------------------
-- KRI 6 — Overdue Mandatory Training (already a daily %)
-- ------------------------------------------------------------
SELECT
    date,
    overdue_training_pct
FROM read_csv_auto('../data/hr_daily.csv')
ORDER BY date;


-- ------------------------------------------------------------
-- Row-level demo: KRI 1 computed from the RAW sample.
-- Proves the failure-rate logic works on individual rows,
-- not just pre-aggregated counts. Mirrors the slide SQL.
-- ------------------------------------------------------------
SELECT
    date,
    error_class,
    COUNT(*)                                                 AS n
FROM read_csv_auto('../data/transactions_sample.csv')
WHERE status = 'FAILED'
  AND error_class IN ('SYSTEM', 'PARTNER')
GROUP BY date, error_class
ORDER BY error_class;
