SELECT
  claim_type_code,
  service_code_system,
  service_code,
  service_display,
  COUNT(*) AS service_count,
  COUNT(DISTINCT eob_id) AS claim_count,
  COUNT(DISTINCT patient_id) AS patient_count,
  SUM(submitted_amount) AS total_submitted_amount,
  SUM(allowed_amount) AS total_allowed_amount,
  SUM(provider_paid_amount) AS total_provider_paid_amount,
  SUM(covered_paid_amount) AS total_covered_paid_amount
FROM healthcare.silver.claim_line
GROUP BY claim_type_code, service_code_system, service_code, service_display;
