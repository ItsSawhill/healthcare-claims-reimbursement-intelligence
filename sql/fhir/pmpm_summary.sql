select
  service_month,
  claim_type_code,
  member_months,
  claim_count,
  pmpm_submitted,
  pmpm_allowed,
  pmpm_provider_paid,
  pmpm_covered_paid,
  pmpm_part_d_plan_paid,
  pmpm_part_d_patient_paid,
  pmpm_drug_cost
from healthcare.gold.pmpm_summary;
