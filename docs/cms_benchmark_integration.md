# CMS Benchmark Integration

## Purpose

This project currently uses synthetic Medicare-style benchmark amounts so the pipeline can run without external data. It is designed to support real CMS Medicare Physician Fee Schedule benchmark files when a local CSV export is available.

The pipeline does not call CMS APIs during execution. That keeps the portfolio project reproducible in CI and avoids breaking the synthetic fallback workflow when network access is unavailable.

## Official CMS References

CMS provides public data and API resources that can support real benchmark integration:

- CMS Data Portal: https://data.cms.gov/
- CMS Data API documentation: https://data.cms.gov/api-docs
- Medicare Physician Fee Schedule datasets: https://pfs.data.cms.gov/datasets
- Medicare Physician Fee Schedule API information: https://pfs.data.cms.gov/about/api

## Expected Local File Format

Place an optional local CMS benchmark file at:

```text
data/raw/cms_benchmarks.csv
```

Required columns:

| Column | Description |
| --- | --- |
| procedure_code | CPT or procedure code used to join against claim procedure codes. |
| benchmark_amount | CMS benchmark amount or fee schedule amount to use for comparison. |
| year | Fee schedule year. The loader uses the latest year available per procedure code. |

Optional columns:

| Column | Description |
| --- | --- |
| locality | CMS locality or pricing locality, if available. |
| state | State or geographic indicator, if available. |

Example:

```csv
procedure_code,benchmark_amount,year,locality,state
99213,92.50,2025,National,NA
99214,128.75,2025,National,NA
93000,18.40,2025,National,NA
```

## How the Loader Works

`src/cms_benchmark_loader.py` checks for a local CMS benchmark CSV. If the file exists, it validates required columns, coerces benchmark amounts and years, and joins benchmark amounts to claims by `procedure_code`.

If no local CMS file exists, or if no procedure codes match, the pipeline keeps the synthetic Medicare-style benchmark amounts generated with the claims data.

The cleaned claims output includes `benchmark_source` so analysts can distinguish synthetic benchmark rows from rows priced with a local CMS file.

## Benchmark Variance Logic

The project calculates benchmark variance as:

```text
benchmark_variance_amount = allowed_amount - medicare_benchmark_amount
benchmark_variance_pct = benchmark_variance_amount / medicare_benchmark_amount
```

Positive variance means allowed reimbursement is above the benchmark. Negative variance means allowed reimbursement is below the benchmark.

## Limitations

- The synthetic benchmark is not official CMS reimbursement data.
- Real CMS Physician Fee Schedule integration may require locality, modifier, year, facility/non-facility, and place-of-service handling.
- This project uses procedure-code matching as a practical portfolio-ready integration pattern.
- Production reimbursement analysis should validate fee schedule interpretation with reimbursement, contracting, and compliance stakeholders.
