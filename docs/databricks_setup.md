# Databricks and Local Spark Setup

## Runtime Requirements

- Python: 3.10 or newer. The local development environment used Python 3.12.
- Spark: Apache Spark 3.5.x through `pyspark`.
- Delta: `delta-spark` 3.2+ for local Delta-enabled sessions, or native Delta support in Databricks Runtime.

The existing pandas claims pipeline remains independent of this Spark FHIR path.

## Local Execution

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Bronze and Silver locally against the synthetic CMS Blue Button fixtures:

```bash
python databricks/01_ingest_fhir_bronze.py \
  --input tests/fixtures/fhir/cms_blue_button \
  --output-root outputs/fhir_spark \
  --output-format parquet
```

Local pytest uses Parquet output semantics and does not require a Databricks workspace.

## Databricks Execution

Upload or sync the repository to Databricks and run:

```bash
python databricks/01_ingest_fhir_bronze.py \
  --input /Volumes/healthcare/raw/fhir \
  --output-root /Volumes/healthcare/curated/fhir \
  --output-format delta \
  --enable-delta
```

Expected logical names:

- `healthcare.bronze.fhir_resources`
- `healthcare.bronze.ingestion_audit`
- `healthcare.silver.patient`
- `healthcare.silver.coverage`
- `healthcare.silver.claim_header`
- `healthcare.silver.claim_line`
- `healthcare.silver.claim_line_financial`
- `healthcare.silver.claim_diagnosis`
- `healthcare.silver.claim_provider`
- `healthcare.silver.data_quality_results`

The current scripts write files to a path. In Databricks, those paths can be registered as managed or external Delta tables with Unity Catalog using the logical names above.

## Delta Versus Local Test Output

Delta is the target table format for Databricks. Local tests default to Parquet because it is available with PySpark without requiring a Delta-enabled Spark catalog.

Use `--output-format delta --enable-delta` only when Delta dependencies are available and the Spark session has Delta extensions configured. Use `--output-format parquet` for portable local development and CI.

Local Delta execution may require Spark to resolve Delta Lake JVM artifacts. If the local environment cannot access Maven repositories, run local tests with Parquet and use Delta in Databricks Runtime, where Delta support is already available.

## Spark Design Notes

Bronze preserves raw FHIR resource JSON with ingestion metadata and validation status. Silver transformations use Spark DataFrame operations including JSON extraction, `from_json`, `explode_outer`, `groupBy`, aggregations, joins, and conditional expressions. The pipeline intentionally stops at Silver; Gold reimbursement analytics and MLflow are reserved for a later phase.
