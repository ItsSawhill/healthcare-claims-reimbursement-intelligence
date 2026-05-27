-- Medicare-style benchmark comparison by provider, service category, region, and payer.

SELECT
    provider_id,
    provider_name,
    service_category,
    region,
    payer,
    COUNT(*) AS total_claims,
    SUM(billed_amount) AS total_billed,
    SUM(allowed_amount) AS total_allowed,
    SUM(paid_amount) AS total_paid,
    SUM(medicare_benchmark_amount) AS medicare_benchmark_total,
    SUM(paid_amount) / NULLIF(SUM(billed_amount), 0) AS paid_to_billed_rate,
    SUM(allowed_amount) / NULLIF(SUM(billed_amount), 0) AS allowed_to_billed_rate,
    SUM(allowed_amount) - SUM(medicare_benchmark_amount) AS benchmark_variance_amount,
    (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) AS benchmark_variance_pct,
    CASE
        WHEN (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) > 0.20
            THEN 'Above benchmark'
        WHEN (SUM(allowed_amount) - SUM(medicare_benchmark_amount)) / NULLIF(SUM(medicare_benchmark_amount), 0) < -0.20
            THEN 'Below benchmark'
        ELSE 'In range'
    END AS benchmark_flag
FROM claims_clean
GROUP BY provider_id, provider_name, service_category, region, payer
ORDER BY benchmark_variance_amount DESC;
