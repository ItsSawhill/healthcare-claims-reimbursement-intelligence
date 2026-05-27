-- Denial analysis by provider, payer, and service category.

SELECT
    provider_id,
    provider_name,
    payer,
    service_category,
    COUNT(*) AS total_claims,
    SUM(denial_flag) AS denied_claims,
    AVG(denial_flag) AS denial_rate,
    SUM(CASE WHEN denial_flag = 1 THEN billed_amount ELSE 0 END) AS denied_billed_amount,
    SUM(CASE WHEN denial_flag = 1 THEN allowed_amount ELSE 0 END) AS denied_allowed_amount,
    SUM(paid_amount) / NULLIF(COUNT(*), 0) AS paid_per_claim
FROM claims_clean
GROUP BY provider_id, provider_name, payer, service_category
HAVING COUNT(*) >= 10
ORDER BY denial_rate DESC, denied_billed_amount DESC;
