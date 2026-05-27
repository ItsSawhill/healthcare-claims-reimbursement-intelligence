-- Candidate anomaly extraction using SQL-friendly thresholds.

WITH claim_stats AS (
    SELECT
        AVG(billed_amount) AS avg_billed,
        STDDEV_POP(billed_amount) AS std_billed
    FROM claims_clean
),
monthly AS (
    SELECT
        DATE_TRUNC('month', service_date) AS service_month,
        SUM(paid_amount) AS total_paid,
        SUM(paid_amount) / NULLIF(MAX(member_months), 0) AS pmpm,
        AVG(denial_flag) AS denial_rate
    FROM claims_clean
    GROUP BY DATE_TRUNC('month', service_date)
),
monthly_stats AS (
    SELECT
        AVG(total_paid) AS avg_paid,
        STDDEV_POP(total_paid) AS std_paid,
        AVG(pmpm) AS avg_pmpm,
        STDDEV_POP(pmpm) AS std_pmpm,
        AVG(denial_rate) AS avg_denial,
        STDDEV_POP(denial_rate) AS std_denial
    FROM monthly
),
provider_candidates AS (
    SELECT
        provider_id,
        provider_name,
        AVG(denial_flag) AS denial_rate,
        (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) AS benchmark_variance_pct,
        SUM(paid_amount) AS total_paid
    FROM claims_clean
    GROUP BY provider_id, provider_name
)
SELECT
    'High billed claim' AS anomaly_type,
    claim_id AS entity_id,
    billed_amount AS metric_value,
    (billed_amount - avg_billed) / NULLIF(std_billed, 0) AS z_score
FROM claims_clean
CROSS JOIN claim_stats
WHERE (billed_amount - avg_billed) / NULLIF(std_billed, 0) > 4

UNION ALL

SELECT
    'Provider financial risk' AS anomaly_type,
    provider_id AS entity_id,
    benchmark_variance_pct AS metric_value,
    NULL AS z_score
FROM provider_candidates
WHERE denial_rate >= 0.18 OR ABS(benchmark_variance_pct) >= 0.25

UNION ALL

SELECT
    'Monthly PMPM spike' AS anomaly_type,
    CAST(service_month AS VARCHAR) AS entity_id,
    pmpm AS metric_value,
    (pmpm - avg_pmpm) / NULLIF(std_pmpm, 0) AS z_score
FROM monthly
CROSS JOIN monthly_stats
WHERE ABS((pmpm - avg_pmpm) / NULLIF(std_pmpm, 0)) > 2;
