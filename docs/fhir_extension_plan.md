# FHIR Extension Plan

## 1. Project Objective

Extend the healthcare claims reimbursement platform so it can ingest synthetic CMS FHIR data, process it with Spark and Databricks, and produce reimbursement analytics while preserving the current flat-file claims pipeline.

## 2. Why FHIR Is Being Added

FHIR support makes the project closer to modern healthcare data exchange patterns. It enables patient, coverage, and adjudicated claim resources to be explored in their source structure before being normalized into analytical tables.

## 3. Proposed Bronze, Silver, and Gold Architecture

Bronze stores raw FHIR JSON resources from local files or a future CMS Blue Button sandbox export. Records should preserve source file, resourceType, resource id, ingestion timestamp, and raw JSON.

Silver normalizes supported resources into patient, coverage, claim-header, and claim-line tables. Silver transformations should use PySpark and keep FHIR-derived fields traceable to their source paths.

Gold contains business-ready reimbursement tables compatible with the existing analytics: claims fact, provider summaries, monthly trends, reimbursement benchmarking, utilization, anomaly candidates, forecasts, and scenario outputs.

## 4. Proposed Databricks Notebook Sequence

1. `00_fhir_data_exploration.py`: local-compatible field exploration and profiling.
2. `01_bronze_fhir_ingest.py`: read raw FHIR JSON into Delta Bronze tables.
3. `02_silver_patient_coverage.py`: normalize Patient and Coverage.
4. `03_silver_eob_claims.py`: normalize ExplanationOfBenefit headers and lines.
5. `04_fhir_data_quality.py`: validate IDs, dates, references, financial paths, and code coverage.
6. `05_gold_claims_analytics_table.py`: create a claim-level analytical table compatible with current pandas outputs.
7. `06_reimbursement_analytics.py`: run adapted reimbursement, PMPM, provider, scenario, anomaly, and forecast analytics.
8. `07_mlflow_tracking.py`: log model/scoring parameters and output metrics when MLflow is introduced.

## 5. Proposed Silver Schemas

`silver_patient`: `patient_id`, `gender`, `birth_date`, `state`, `postal_code`, source metadata.

`silver_coverage`: `coverage_id`, `patient_id`, `coverage_status`, `coverage_start`, `coverage_end`, payer or insurer reference, source metadata.

`silver_claim_header`: `eob_id`, `patient_id`, `coverage_id`, `claim_status`, `claim_type`, `service_start`, `service_end`, `provider_reference`, `insurer_reference`, payment amount candidates, source metadata.

`silver_claim_line`: `eob_id`, `line_sequence`, `procedure_code`, diagnosis references or diagnosis codes when present, line service dates, observed adjudication category codes, candidate amount paths, source metadata.

## 6. Existing Analytics That Will Be Reused

Existing claims summaries, PMPM calculations, reimbursement benchmarking, provider KPIs, provider segmentation, cost-driver analytics, anomaly detection, forecasting, scenario simulation, reporting, Streamlit views, and SQL patterns can be reused after FHIR data is converted into a compatible Gold claims table.

## 7. New Analytics Enabled by FHIR

FHIR can enable coverage-period-aware member-month calculations, claim header versus line-level service analytics, adjudication category completeness checks, patient demographics segmentation, EOB status monitoring, resource linkage quality, and drill-down from dashboard measures to source FHIR paths.

## 8. Data-Quality Checks

Validate resourceType coverage, resource IDs, Bundle entry shape, duplicate IDs, patient and coverage references, claim status values, service date ranges, coverage date ranges, missing demographic fields, procedure and diagnosis code presence, financial amount path coverage, adjudication category code coverage, negative or null amount candidates, and header-to-line row counts.

## 9. Testing Strategy

Keep local unit tests for JSON loading, Bundle extraction, malformed entries, missing resourceType, missing IDs, nested path profiling, EOB claim type detection, adjudication category discovery, financial path candidates, and service date ranges.

Add Spark tests only when transformations are introduced. Those tests should use tiny local fixtures and compare Silver/Gold schemas and row counts. Existing pandas pipeline tests should continue to run unchanged.

## 10. Phased Implementation Plan

Phase 1 adds isolated FHIR exploration utilities, documentation, field mapping, and tests.

Phase 2 adds representative synthetic CMS FHIR fixtures and finalizes field mappings based on observed profiles.

Phase 3 builds Bronze and Silver PySpark transformations with Delta-ready schemas.

Phase 4 builds Gold reimbursement analytics tables and adapters into the existing analytics modules.

Phase 5 adds Databricks SQL dashboards and MLflow tracking for scoring, anomaly, and forecast outputs.
