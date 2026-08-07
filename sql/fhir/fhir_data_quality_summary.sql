SELECT
  'ExplanationOfBenefit' AS resource_type,
  claim_type_code,
  'EOBs with patient reference' AS metric_name,
  SUM(CASE WHEN patient_id IS NOT NULL THEN 1 ELSE 0 END) AS numerator,
  COUNT(*) AS denominator,
  SUM(CASE WHEN patient_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) AS percentage
FROM healthcare.silver.claim_header
GROUP BY claim_type_code;
