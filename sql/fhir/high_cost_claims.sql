-- Cost basis must be claim-type-aware; this query mirrors the Phase 3 Spark rule.
WITH claim_cost AS (
  SELECT
    eob_id,
    patient_id,
    claim_type_code,
    SUM(provider_paid_amount) AS provider_paid_amount,
    SUM(allowed_amount) AS allowed_amount,
    SUM(covered_paid_amount) AS covered_paid_amount
  FROM healthcare.silver.claim_line
  GROUP BY eob_id, patient_id, claim_type_code
),
pde_cost AS (
  SELECT
    eob_id,
    SUM(CASE WHEN analytical_category = 'part_d_total_drug_cost' THEN amount END) AS total_drug_cost,
    SUM(CASE WHEN analytical_category = 'part_d_plan_paid_amount' THEN amount END) AS part_d_plan_paid
  FROM healthcare.silver.claim_line_financial
  GROUP BY eob_id
)
SELECT
  c.eob_id,
  c.patient_id,
  c.claim_type_code,
  CASE
    WHEN c.claim_type_code = 'CARRIER' THEN 'provider_paid_amount'
    WHEN c.claim_type_code = 'OUTPATIENT' THEN 'covered_paid_amount'
    WHEN c.claim_type_code = 'PDE' THEN 'part_d_total_drug_cost'
    ELSE 'unsupported'
  END AS cost_basis_name,
  CASE
    WHEN c.claim_type_code = 'CARRIER' THEN c.provider_paid_amount
    WHEN c.claim_type_code = 'OUTPATIENT' THEN c.covered_paid_amount
    WHEN c.claim_type_code = 'PDE' THEN p.total_drug_cost
  END AS cost_basis_amount
FROM claim_cost c
LEFT JOIN pde_cost p ON c.eob_id = p.eob_id;
