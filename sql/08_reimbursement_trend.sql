-- Reimbursement trend by provider and service category.

SELECT
    DATE_TRUNC('month', service_date) AS service_month,
    provider_id,
    provider_name,
    service_category,
    COUNT(*) AS total_claims,
    SUM(billed_amount) AS total_billed,
    SUM(allowed_amount) AS total_allowed,
    SUM(paid_amount) AS total_paid,
    SUM(paid_amount) / NULLIF(SUM(billed_amount), 0) AS paid_to_billed_rate,
    SUM(allowed_amount) / NULLIF(SUM(billed_amount), 0) AS allowed_to_billed_rate,
    (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) AS benchmark_variance_pct
FROM claims_clean
GROUP BY DATE_TRUNC('month', service_date), provider_id, provider_name, service_category
ORDER BY service_month, benchmark_variance_pct DESC;
