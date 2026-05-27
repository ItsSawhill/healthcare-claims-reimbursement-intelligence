# Architecture

## Overview

This project is organized as a repeatable healthcare claims analytics pipeline. The workflow starts with raw or synthetic claim-level data and ends with dashboard-ready tables, presentation-quality figures, SQL analytics patterns, and an executive report.

```text
data/raw/claims.csv
        |
        v
Ingestion Layer
src/ingest.py
        |
        v
Preprocessing Layer
src/preprocess.py
        |
        v
Clean Claims Table
data/processed/claims_clean.csv
        |
        +--------------------+-------------------+--------------------+
        |                    |                   |                    |
        v                    v                   v                    v
Claims Analytics     Utilization Analytics  Reimbursement       Provider Analytics
monthly trends       PMPM, visits/1,000     benchmark variance  risk scoring
cost summaries       cost per visit         paid/billed rates   clustering
        |                    |                   |                    |
        +--------------------+-------------------+--------------------+
                             |
                             v
        +--------------------+-------------------+
        |                                        |
        v                                        v
Anomaly Detection                      Forecasting
z-score, IQR, risk rules               rolling average + smoothing
        |                                        |
        +--------------------+-------------------+
                             |
                             v
Scenario Simulation
rate, utilization, contract, and benchmark alignment impact
                             |
                             v
Reporting and BI Outputs
outputs/tables + outputs/figures + outputs/reports
```

## Data Ingestion Layer

`src/ingest.py` loads `data/raw/claims.csv` when a claims extract exists. If no raw file is present, it generates a 20,000-row synthetic healthcare claims dataset with realistic variation by provider, payer, region, service category, diagnosis, and procedure.

The synthetic dataset includes injected business anomalies so downstream analytics can identify meaningful review candidates:

- high billed outpatient claims
- provider denial spikes
- reimbursement drops
- PMPM spikes in high-acuity categories

## Preprocessing Layer

`src/preprocess.py` validates required fields, parses dates, removes duplicate claim IDs, coerces numeric fields, clips negative amounts, applies denial logic, and derives service month fields.

The cleaned output is saved to:

```text
data/processed/claims_clean.csv
```

## Analytics Layer

The analytics layer produces reusable, dashboard-ready views:

- `claims_analytics.py`: monthly cost trends and dimensional summaries
- `utilization.py`: visits per 1,000, cost per visit, cost per member, claims per member, PMPM
- `reimbursement.py`: paid-to-billed rate, allowed-to-billed rate, benchmark variance
- `provider_kpis.py`: provider-level cost, denial, reimbursement, and efficiency measures
- `advanced_analytics.py`: provider risk scoring, weighted efficiency scoring, reimbursement deviation severity, clustering, and cost driver analysis
- `scenario_simulation.py`: reimbursement rate, utilization, provider contract, and benchmark alignment impact modeling
- `cms_benchmark_loader.py`: optional local CMS benchmark file validation with synthetic benchmark fallback

## Forecasting Layer

`src/forecasting.py` forecasts:

- total paid amount
- claim volume
- PMPM

The model is intentionally explainable. It blends a three-month rolling average, exponential smoothing, and recent slope adjustment. This provides a practical baseline before introducing heavier time-series models.

## Anomaly Detection Layer

`src/anomaly_detection.py` flags candidates for operational review using:

- z-score thresholds for high billed claims
- IQR outlier checks
- provider financial risk rules
- benchmark variance thresholds
- monthly PMPM, denial rate, and total paid trend breaks

The output is an explainable candidate list, not an automated fraud determination.

## Reporting Layer

`src/reporting.py` produces:

- executive summary report
- cost trend figures
- PMPM trend
- reimbursement variance visuals
- denial distribution
- provider efficiency/risk ranking
- anomaly frequency by month
- utilization trend dashboard plot
- scenario financial impact plots
- executive Excel workbook with scenario tabs

The executive report is written to:

```text
outputs/reports/executive_summary.md
```

## BI and Dashboard Layer

The pipeline saves clean CSV outputs in `outputs/tables/` for Tableau, Power BI, Looker, Streamlit, Excel, or SQL-based dashboarding.

Core outputs include:

- `provider_kpis.csv`
- `monthly_trends.csv`
- `reimbursement_benchmarking.csv`
- `utilization_summary.csv`
- `cost_driver_analysis.csv`
- `anomalies.csv`
- `forecast_summary.csv`
- `scenario_summary.csv`
- `scenario_rate_change.csv`
- `scenario_utilization_change.csv`
- `scenario_provider_contract_change.csv`
- `scenario_benchmark_alignment.csv`

These tables are intentionally denormalized and readable so analysts and hiring managers can inspect the business logic without needing a database.
