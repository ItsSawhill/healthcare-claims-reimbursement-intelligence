select
  patient_id,
  total_cost_basis,
  claim_count,
  claim_line_count,
  active_months,
  cost_per_active_month,
  population_percentile,
  top_10_pct_flag,
  top_20_pct_flag,
  cumulative_spend_share
from healthcare.gold.patient_spending_concentration
order by total_cost_basis desc;
