-- Utilization trend for service category monitoring.

SELECT
    DATE_TRUNC('month', service_date) AS service_month,
    service_category,
    COUNT(*) AS visits,
    COUNT(DISTINCT member_id) AS unique_members,
    MAX(member_months) AS member_months,
    COUNT(*) * 1000.0 / NULLIF(MAX(member_months), 0) AS visits_per_1000_members,
    SUM(paid_amount) / NULLIF(COUNT(*), 0) AS cost_per_visit,
    SUM(paid_amount) / NULLIF(COUNT(DISTINCT member_id), 0) AS cost_per_member,
    SUM(paid_amount) / NULLIF(MAX(member_months), 0) AS pmpm
FROM claims_clean
GROUP BY DATE_TRUNC('month', service_date), service_category
ORDER BY service_month, pmpm DESC;
