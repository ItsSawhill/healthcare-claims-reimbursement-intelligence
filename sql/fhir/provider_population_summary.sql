select
  provider_identifier,
  provider_role,
  provider_source,
  patient_count,
  claim_count,
  claim_line_count,
  unique_service_count,
  attributable_cost_basis_total,
  average_cost_per_claim,
  average_cost_per_patient,
  provider_volume_percentile,
  provider_cost_percentile
from healthcare.gold.provider_population_summary;
