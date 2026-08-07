SELECT
  claim_type_code,
  analytical_category,
  adjudication_code,
  adjudication_display,
  COUNT(*) AS record_count,
  COUNT(DISTINCT eob_id) AS claim_count,
  COUNT(DISTINCT CONCAT(eob_id, ':', line_number)) AS claim_line_count,
  SUM(amount) AS total_amount,
  AVG(amount) AS avg_amount,
  percentile_approx(amount, 0.5) AS median_amount,
  MIN(amount) AS min_amount,
  MAX(amount) AS max_amount
FROM healthcare.silver.claim_line_financial
GROUP BY claim_type_code, analytical_category, adjudication_code, adjudication_display;
