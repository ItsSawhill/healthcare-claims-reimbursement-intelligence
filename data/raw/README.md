# Raw Data

This folder is for local source files used by the pipeline.

## Synthetic Claims

The project can generate synthetic claims automatically when `data/raw/claims.csv` is not present. The synthetic claims layer is a simulated claim-level dataset for portfolio analytics. It is not real patient-level claims data.

## Optional CMS Public Provider/Service Data

To add a real public Medicare benchmark layer, manually download the CMS Medicare Physician & Other Practitioners by Provider and Service dataset from:

https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider-and-service

Save the CSV locally as:

```text
data/raw/cms_provider_service.csv
```

This CMS file can be large and is intentionally ignored by git. Do not commit the full CMS raw CSV, ZIP, or Parquet file.

When the file is present, `python src/run_pipeline.py` creates public Medicare benchmark outputs in:

```text
outputs/tables/cms_provider_service_benchmarks.csv
```

When the file is absent, the project continues to run with the synthetic Medicare-style benchmark fallback.
