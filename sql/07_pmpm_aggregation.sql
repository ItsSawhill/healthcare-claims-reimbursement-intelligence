-- PMPM aggregation by month, payer, region, and service category.

SELECT
    DATE_TRUNC('month', service_date) AS service_month,
    payer,
    region,
    service_category,
    COUNT(*) AS total_claims,
    COUNT(DISTINCT member_id) AS unique_members,
    MAX(member_months) AS member_months,
    SUM(paid_amount) AS total_paid,
    SUM(paid_amount) / NULLIF(MAX(member_months), 0) AS pmpm,
    COUNT(*) * 1000.0 / NULLIF(MAX(member_months), 0) AS visits_per_1000_members
FROM claims_clean
GROUP BY DATE_TRUNC('month', service_date), payer, region, service_category
ORDER BY service_month, total_paid DESC;
