-- Claims summary by common dashboard dimensions.
-- Assumes a cleaned claims table or view named claims_clean.

SELECT
    service_category,
    payer,
    region,
    COUNT(*) AS total_claims,
    COUNT(DISTINCT member_id) AS unique_members,
    SUM(billed_amount) AS total_billed,
    SUM(allowed_amount) AS total_allowed,
    SUM(paid_amount) AS total_paid,
    SUM(member_responsibility) AS member_responsibility,
    SUM(denial_flag) AS denied_claims,
    AVG(denial_flag) AS denial_rate,
    SUM(paid_amount) / NULLIF(SUM(billed_amount), 0) AS paid_to_billed_rate
FROM claims_clean
GROUP BY service_category, payer, region
ORDER BY total_paid DESC;
