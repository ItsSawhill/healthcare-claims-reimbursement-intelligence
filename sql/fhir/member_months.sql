select
  patient_id,
  coverage_month,
  coverage_active_flag,
  coverage_type_code,
  source_coverage_id,
  source_dataset
from healthcare.gold.member_months;
