-- Provider risk scoring using explainable weighted components.

WITH provider_base AS (
    SELECT
        provider_id,
        provider_name,
        region,
        COUNT(*) AS total_claims,
        SUM(paid_amount) AS total_paid,
        SUM(billed_amount) AS total_billed,
        SUM(allowed_amount) AS total_allowed,
        AVG(denial_flag) AS denial_rate,
        SUM(paid_amount) / NULLIF(COUNT(*), 0) AS average_cost_per_claim,
        SUM(paid_amount) / NULLIF(MAX(member_months), 0) AS pmpm_contribution,
        (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) AS benchmark_variance_pct
    FROM claims_clean
    GROUP BY provider_id, provider_name, region
),
scored AS (
    SELECT
        *,
        PERCENT_RANK() OVER (ORDER BY average_cost_per_claim) AS cost_rank,
        PERCENT_RANK() OVER (ORDER BY denial_rate) AS denial_rank,
        PERCENT_RANK() OVER (ORDER BY pmpm_contribution) AS pmpm_rank,
        PERCENT_RANK() OVER (ORDER BY ABS(benchmark_variance_pct)) AS benchmark_rank,
        PERCENT_RANK() OVER (ORDER BY total_paid) AS paid_rank
    FROM provider_base
)
SELECT
    *,
    ROUND(
        100 * (
            0.25 * cost_rank
            + 0.25 * denial_rank
            + 0.20 * pmpm_rank
            + 0.20 * benchmark_rank
            + 0.10 * paid_rank
        ),
        2
    ) AS provider_risk_score,
    CASE
        WHEN 100 * (0.25 * cost_rank + 0.25 * denial_rank + 0.20 * pmpm_rank + 0.20 * benchmark_rank + 0.10 * paid_rank) >= 70 THEN 'Critical'
        WHEN 100 * (0.25 * cost_rank + 0.25 * denial_rank + 0.20 * pmpm_rank + 0.20 * benchmark_rank + 0.10 * paid_rank) >= 45 THEN 'High'
        WHEN 100 * (0.25 * cost_rank + 0.25 * denial_rank + 0.20 * pmpm_rank + 0.20 * benchmark_rank + 0.10 * paid_rank) >= 25 THEN 'Moderate'
        ELSE 'Low'
    END AS provider_risk_tier
FROM scored
ORDER BY provider_risk_score DESC;
