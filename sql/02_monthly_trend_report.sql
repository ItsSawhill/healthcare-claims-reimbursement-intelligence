-- Monthly claims trend report with PMPM and utilization metrics.

SELECT
    DATE_TRUNC('month', service_date) AS service_month,
    COUNT(*) AS total_claims,
    COUNT(DISTINCT member_id) AS unique_members,
    MAX(member_months) AS member_months,
    SUM(billed_amount) AS total_billed,
    SUM(allowed_amount) AS total_allowed,
    SUM(paid_amount) AS total_paid,
    SUM(member_responsibility) AS member_responsibility,
    SUM(denial_flag) AS denied_claims,
    AVG(denial_flag) AS denial_rate,
    SUM(paid_amount) / NULLIF(MAX(member_months), 0) AS pmpm,
    COUNT(*) * 1000.0 / NULLIF(MAX(member_months), 0) AS visits_per_1000_members
FROM claims_clean
GROUP BY DATE_TRUNC('month', service_date)
ORDER BY service_month;
