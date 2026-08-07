# Phase 4 Spark Engineering Notes

## Major Spark Operations

- Bronze uses JSON reads, Bundle entry explosion, resource validation, provenance extraction, and duplicate-aware windowing by source/resource identity.
- Silver uses `select`, `from_json`, `explode_outer`, `regexp_extract`, `groupBy`, and joins to normalize EOB headers, lines, diagnoses, providers, and adjudication records.
- Gold uses `groupBy`, `sum`, `avg`, `countDistinct`, `percentile_approx`, joins, and window functions for claim-type summaries, service summaries, PMPM, provider population analytics, and concentration metrics.

## Expected Shuffles

- Bronze de-duplication shuffles by `source_system`, `source_dataset`, `resource_type`, and `resource_id`.
- Financial aggregation shuffles by `eob_id`, `line_number`, and adjudication category.
- Gold summaries shuffle by claim type, service code system, provider, patient, and month.
- Ranking windows for spending concentration and provider percentiles use global ordering. On the small local synthetic cohort this is acceptable, but larger datasets should partition or materialize intermediate aggregates before ranking.

## Partition Considerations

Local execution uses a small Spark session with `spark.sql.shuffle.partitions=4`. Databricks jobs should tune partitions based on input size and cluster capacity.

## Caching

No persistent caching is required for the current local dataset. In Databricks, Bronze and Silver tables should be materialized as Delta tables before Gold aggregation.

## Performance Metrics

Basic execution metrics are written to:

`outputs/metrics/fhir_population_performance.json`

These are engineering run metrics, not benchmark claims.
