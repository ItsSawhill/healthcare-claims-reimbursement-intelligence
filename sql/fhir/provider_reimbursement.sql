-- Provider money allocation should only be applied when provider attribution is unambiguous.
WITH provider_counts AS (
  SELECT eob_id, COUNT(*) AS provider_rows_for_eob
  FROM healthcare.silver.claim_provider
  GROUP BY eob_id
),
provider_line AS (
  SELECT
    p.provider_identifier,
    p.provider_reference,
    p.provider_role_code,
    p.provider_role_display,
    p.provider_source,
    l.claim_type_code,
    l.eob_id,
    l.patient_id,
    l.line_number,
    l.service_code,
    CASE WHEN pc.provider_rows_for_eob = 1 THEN l.submitted_amount END AS submitted_amount,
    CASE WHEN pc.provider_rows_for_eob = 1 THEN l.allowed_amount END AS allowed_amount,
    CASE WHEN pc.provider_rows_for_eob = 1 THEN l.provider_paid_amount END AS provider_paid_amount,
    CASE WHEN pc.provider_rows_for_eob = 1 THEN l.covered_paid_amount END AS covered_paid_amount
  FROM healthcare.silver.claim_provider p
  JOIN provider_counts pc ON p.eob_id = pc.eob_id
  LEFT JOIN healthcare.silver.claim_line l ON p.eob_id = l.eob_id AND p.patient_id = l.patient_id
)
SELECT
  provider_identifier,
  provider_reference,
  provider_role_code,
  provider_role_display,
  provider_source,
  claim_type_code,
  COUNT(DISTINCT eob_id) AS claim_count,
  COUNT(DISTINCT CONCAT(eob_id, ':', line_number)) AS claim_line_count,
  COUNT(DISTINCT patient_id) AS patient_count,
  COUNT(DISTINCT service_code) AS service_count,
  SUM(submitted_amount) AS total_submitted_amount,
  SUM(allowed_amount) AS total_allowed_amount,
  SUM(provider_paid_amount) AS total_provider_paid_amount,
  SUM(covered_paid_amount) AS total_covered_paid_amount
FROM provider_line
GROUP BY provider_identifier, provider_reference, provider_role_code, provider_role_display, provider_source, claim_type_code;
