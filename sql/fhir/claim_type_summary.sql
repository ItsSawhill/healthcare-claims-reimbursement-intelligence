SELECT
  claim_type_code,
  COUNT(DISTINCT eob_id) AS claim_count,
  COUNT(*) AS claim_line_count,
  COUNT(DISTINCT patient_id) AS unique_patient_count,
  MIN(service_date) AS service_date_min,
  MAX(service_date) AS service_date_max,
  SUM(submitted_amount) AS total_submitted_amount,
  SUM(allowed_amount) AS total_allowed_amount,
  SUM(provider_paid_amount) AS total_provider_paid_amount,
  SUM(covered_paid_amount) AS total_covered_paid_amount,
  SUM(beneficiary_paid_amount) AS total_beneficiary_paid_amount
FROM healthcare.silver.claim_line
GROUP BY claim_type_code;
