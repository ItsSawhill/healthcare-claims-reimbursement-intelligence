# Real CMS Public Data Integration

## What This Adds

This project uses synthetic claims for claim-level simulation and optional CMS public data for Medicare reimbursement benchmarking.

It does not use real patient-level private claims. Real patient-level claims are not public. The CMS layer is a public provider/service utilization and payment reference layer that can improve benchmark realism without introducing protected health information.

## CMS Dataset

Optional source:

CMS Medicare Physician & Other Practitioners by Provider and Service

https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider-and-service

This public dataset summarizes Medicare utilization and payment by provider and service. It is useful for reimbursement analytics because it includes provider, state, HCPCS/procedure code, service counts, submitted charges, Medicare allowed amounts, and Medicare payment amounts.

The project also preserves Medicare Physician Fee Schedule readiness:

- https://data.cms.gov/
- https://data.cms.gov/api-docs
- https://pfs.data.cms.gov/datasets
- https://pfs.data.cms.gov/about/api

## How This Differs From Private Claims

Synthetic claims in this repository are simulated claim-level records used to demonstrate claims analytics, PMPM, provider ranking, anomaly detection, forecasting, and scenario modeling.

CMS public provider/service data is not patient-level claims data. It is aggregated public Medicare data that can be used as a benchmark reference for procedure-level reimbursement, allowed amount, payment, and charge ratios.

## Download Instructions

1. Visit the CMS provider/service dataset page:
   https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider-and-service
2. Download the CSV version of the dataset.
3. Save the file locally as:

```text
data/raw/cms_provider_service.csv
```

4. Run:

```bash
python src/run_pipeline.py
```

5. Review:

```text
outputs/tables/cms_provider_service_benchmarks.csv
data/processed/claims_clean.csv
```

The raw CMS file may be large and is intentionally ignored by git.

## Expected Fields

The loader standardizes common CMS export field names into:

| Standard Field | Meaning |
| --- | --- |
| provider_npi | Rendering provider NPI. |
| provider_name | Provider name or organization name. |
| provider_state | Provider state. |
| procedure_code | HCPCS or procedure code. |
| service_description | HCPCS/service description. |
| number_of_services | Number of Medicare services. |
| submitted_charge_amount | Average submitted charge amount from CMS export. |
| medicare_allowed_amount | Average Medicare allowed amount from CMS export. |
| medicare_payment_amount | Average Medicare payment amount from CMS export. |

The loader supports common CMS-style names such as `Rndrng_NPI`, `Rndrng_Prvdr_State_Abrvtn`, `HCPCS_Cd`, `HCPCS_Desc`, `Tot_Srvcs`, `Avg_Sbmtd_Chrg`, `Avg_Mdcr_Alowd_Amt`, and `Avg_Mdcr_Pymt_Amt`.

## Generated Benchmark Metrics

When the CMS file exists, the pipeline creates:

```text
outputs/tables/cms_provider_service_benchmarks.csv
```

Benchmark metrics include:

- average submitted charge
- average Medicare allowed amount
- average Medicare payment amount
- Medicare payment-to-charge ratio
- allowed-to-charge ratio
- procedure-code benchmarks
- provider-state benchmarks
- service-category benchmark row when mappable

## Synthetic-to-CMS Join

When possible, synthetic claims are joined to CMS benchmarks using:

```text
synthetic_claims.procedure_code = cms_provider_service.HCPCS_Cd
```

The processed claims table receives:

- `cms_avg_submitted_charge`
- `cms_avg_medicare_allowed`
- `cms_avg_medicare_payment`
- `cms_allowed_variance`
- `cms_payment_variance`
- `cms_benchmark_source`

If CMS data is missing, these fields remain empty or simulated and the existing Medicare-style synthetic benchmark remains active.

## Benchmark Variance

CMS benchmark variance is calculated as:

```text
cms_allowed_variance = synthetic_allowed_amount - cms_avg_medicare_allowed
cms_payment_variance = synthetic_paid_amount - cms_avg_medicare_payment
```

The main benchmark variance logic remains:

```text
benchmark_variance_amount = allowed_amount - benchmark_amount
benchmark_variance_pct = benchmark_variance_amount / benchmark_amount
```

When CMS provider/service data is available and a procedure code matches, `benchmark_amount` is represented by CMS average Medicare allowed amount. Otherwise, the project uses the simulated Medicare-style benchmark.

## What Changes When CMS Data Is Present

When `data/raw/cms_provider_service.csv` exists:

- CMS public provider/service benchmarks are created.
- Synthetic claims are enriched by HCPCS/procedure code where possible.
- Benchmark source is labeled as `CMS Medicare Physician & Other Practitioners public data` for matched rows.
- Scenario benchmark alignment uses CMS allowed benchmarks where available.
- Reimbursement variance analysis becomes anchored to real public Medicare aggregate payment/utilization data for matching procedure codes.

When the CMS file is absent:

- The pipeline logs a clear fallback message.
- Synthetic benchmark logic remains active.
- The pipeline, dashboard, tests, Excel workbook, and scenario outputs continue to run.

## Limitations

- CMS public provider/service data is aggregated and not patient-level.
- Matching is based on procedure/HCPCS code only in this portfolio implementation.
- Production analysis may need locality, specialty, facility/non-facility status, modifier, year, and contract-specific logic.
- CMS public Medicare benchmarks may not represent commercial, Medicaid, exchange, or negotiated provider contract reimbursement.
