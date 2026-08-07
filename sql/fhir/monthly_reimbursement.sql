SELECT
  DATE_TRUNC('month', service_date) AS service_month,
  claim_type_code,
  COUNT(DISTINCT eob_id) AS claim_count,
  COUNT(*) AS claim_line_count,
  COUNT(DISTINCT service_code) AS unique_service_count,
  SUM(submitted_amount) AS total_submitted_amount,
  SUM(allowed_amount) AS total_allowed_amount,
  SUM(provider_paid_amount) AS total_provider_paid_amount,
  SUM(covered_paid_amount) AS total_covered_paid_amount,
  SUM(beneficiary_paid_amount) AS total_beneficiary_paid_amount
FROM healthcare.silver.claim_line
GROUP BY DATE_TRUNC('month', service_date), claim_type_code;
