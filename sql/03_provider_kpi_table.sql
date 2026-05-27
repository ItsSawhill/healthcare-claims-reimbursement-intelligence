-- Provider KPI table for reimbursement and cost-efficiency monitoring.

WITH provider_base AS (
    SELECT
        provider_id,
        provider_name,
        region,
        COUNT(*) AS total_claims,
        SUM(denial_flag) AS denied_claims,
        SUM(billed_amount) AS total_billed,
        SUM(allowed_amount) AS total_allowed,
        SUM(paid_amount) AS total_paid,
        SUM(member_responsibility) AS member_responsibility,
        MAX(member_months) AS member_months,
        COUNT(DISTINCT member_id) AS unique_members,
        SUM(medicare_benchmark_amount) AS medicare_benchmark_total
    FROM claims_clean
    GROUP BY provider_id, provider_name, region
)
SELECT
    provider_id,
    provider_name,
    region,
    total_claims,
    total_billed,
    total_allowed,
    total_paid,
    total_paid / NULLIF(total_claims, 0) AS average_cost_per_claim,
    total_paid / NULLIF(total_billed, 0) AS reimbursement_rate,
    denied_claims * 1.0 / NULLIF(total_claims, 0) AS denial_rate,
    total_paid / NULLIF(member_months, 0) AS pmpm_contribution,
    total_allowed - medicare_benchmark_total AS benchmark_variance_amount,
    (total_allowed - medicare_benchmark_total) / NULLIF(medicare_benchmark_total, 0) AS benchmark_variance_pct
FROM provider_base
ORDER BY total_paid DESC;
