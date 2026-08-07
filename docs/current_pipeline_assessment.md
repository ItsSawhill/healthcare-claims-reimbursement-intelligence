# Current Pipeline Assessment

## 1. Current Ingestion Flow

The current pipeline starts in `src/run_pipeline.py`. It loads `data/raw/claims.csv` through `src/ingest.py`; if that file is absent, it generates a 20,000-row synthetic claims CSV and a 500-row sample file. Optional local CMS benchmark files are read from `data/raw/cms_benchmarks.csv` and `data/raw/cms_provider_service.csv`.

`src/preprocess.py` validates the flat claims schema, parses `service_date` and `paid_date`, removes duplicate `claim_id` values, coerces amount fields to nonnegative numeric values, applies denial logic, and derives `service_month`, `paid_month`, `claim_count`, and `is_paid_claim`.

## 2. Current Processed Tables or Dataframes

The primary processed table is `data/processed/claims_clean.csv`. It is a claim-level analytical table with member, provider, date, diagnosis, procedure, payer, region, amount, denial, member-month, and benchmark fields.

Pipeline dataframes include monthly trends, reimbursement benchmarking, provider KPIs, utilization summaries, high-utilization segments, cost-driver analysis, anomaly candidates, forecasts, and scenario outputs.

## 3. Current Analytics Outputs

Dashboard-ready CSVs are written to `outputs/tables/`, including `monthly_trends.csv`, `provider_kpis.csv`, `reimbursement_benchmarking.csv`, `utilization_summary.csv`, `cost_driver_analysis.csv`, `anomalies.csv`, `forecast_summary.csv`, scenario tables, and claims summaries by month, provider, procedure, diagnosis, region, payer, and service category.

Figures are written to `outputs/figures/`, including PMPM trend, monthly cost trend, provider risk ranking, reimbursement variance, denial distribution, utilization dashboard, anomaly frequency, forecasts, and scenario impact charts.

## 4. Current Model Outputs

The project does not train a persistent model artifact. Existing analytical modeling includes provider clustering with scikit-learn KMeans, rule-based provider risk scoring, z-score/IQR anomaly detection, and baseline forecasting using rolling average, exponential smoothing, and recent trend.

## 5. Components That Can Be Reused Directly

The existing pandas analytics can be reused once FHIR resources are normalized into claim-like analytical tables with compatible columns:

- `claims_analytics.py` for dimensional claims summaries and monthly trends.
- `reimbursement.py` for paid-to-billed, allowed-to-billed, and benchmark variance calculations.
- `provider_kpis.py` and `advanced_analytics.py` for provider risk, segmentation, reimbursement deviation, and cost-driver analytics.
- `utilization.py` for PMPM, visits per 1,000, and cost-per-visit outputs.
- `anomaly_detection.py` after FHIR-normalized fields match current column expectations.
- `forecasting.py` for monthly paid, claim count, and PMPM forecasts.
- `scenario_simulation.py` after EOB financial amounts are mapped into billed, allowed, paid, member responsibility, denial, and benchmark fields.
- `reporting.py`, `app.py`, and SQL scripts if Gold tables preserve the current output table schemas.

## 6. Components Requiring Adapters

FHIR support should add adapters that transform Patient, Coverage, and ExplanationOfBenefit into Silver patient, coverage, claim-header, and claim-line tables, then into a Gold claims analytics table compatible with the existing pipeline.

Required adapters include patient/member ID mapping, provider reference/NPI extraction, claim header and claim line flattening, diagnosis/procedure extraction, service date derivation, adjudication amount mapping, claim status to denial flag logic, member-month derivation from coverage periods, service category derivation, and benchmark attachment.

## 7. Components Tightly Coupled to CSV Schemas

`src/ingest.py` and `src/preprocess.py` are tightly coupled to `data/raw/claims.csv` and the required flat-file columns. Most downstream modules assume columns such as `claim_id`, `member_id`, `provider_id`, `provider_name`, `service_date`, `paid_date`, `diagnosis_code`, `procedure_code`, `service_category`, `billed_amount`, `allowed_amount`, `paid_amount`, `member_responsibility`, `denial_flag`, `region`, `payer`, `member_months`, and `medicare_benchmark_amount`.

The Streamlit dashboard and report generation also assume current `outputs/tables/` names and columns.

## 8. Risks of Adding FHIR Support

FHIR `ExplanationOfBenefit` financial amounts are often represented through adjudication categories whose code meanings must be confirmed from the actual synthetic CMS profile. Mapping submitted, allowed, paid, and patient responsibility amounts prematurely could produce misleading reimbursement analytics.

Other risks include variable Bundle structures, missing IDs, multiple patient addresses or coverage periods, claim header versus line-level dates, provider references that do not resolve to usable provider names, line-level procedure and diagnosis cardinality, member-month derivation from coverage rather than claims, and performance differences when moving from pandas to Spark.

## 9. Recommended Migration Strategy

Preserve the current flat-file pipeline and add a parallel FHIR path. First profile real sample FHIR JSON locally, then build Spark Bronze tables that retain raw resources. Next create Silver patient, coverage, claim-header, and claim-line tables with explicit data-quality checks. After financial and code mappings are validated, create a Gold claims table that matches the existing analytics schema and run the current analytics against it. Only then add Databricks SQL dashboards and MLflow tracking.
