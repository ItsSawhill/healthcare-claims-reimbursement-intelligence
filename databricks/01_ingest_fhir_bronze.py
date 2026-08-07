"""Run local/Databricks-compatible FHIR Bronze and Silver ingestion.

Despite the notebook-style name, this script is standard Python so it can run in
local pytest/CLI workflows and in Databricks jobs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fhir.spark.bronze import build_ingestion_audit, create_spark_session, read_bronze_resources, write_dataframe
from fhir.spark.quality import build_data_quality_results, summarize_quality_results
from fhir.spark.silver import build_pipeline_summary, build_silver_tables, write_silver_tables


def _single_csv_from_spark_dir(tmp_dir: Path, target: Path) -> None:
    part_files = sorted(tmp_dir.glob("part-*.csv"))
    if not part_files:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(part_files[0], target)
    shutil.rmtree(tmp_dir)


def _write_summary_artifacts(summary: dict, quality, claim_header, output_root: Path) -> None:
    metrics_dir = output_root / "metrics"
    tables_dir = output_root / "tables"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "silver_pipeline_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    quality_tmp = tables_dir / "silver_data_quality_summary.csv.tmp"
    summarize_quality_results(quality).coalesce(1).write.mode("overwrite").option("header", True).csv(str(quality_tmp))
    _single_csv_from_spark_dir(quality_tmp, tables_dir / "silver_data_quality_summary.csv")

    claim_type_tmp = tables_dir / "silver_claim_type_summary.csv.tmp"
    claim_header.groupBy("claim_type_code").count().coalesce(1).write.mode("overwrite").option("header", True).csv(str(claim_type_tmp))
    _single_csv_from_spark_dir(claim_type_tmp, tables_dir / "silver_claim_type_summary.csv")


def _print_counts(bronze, audit, silver, quality, summary: dict) -> None:
    print("FHIR Resources")
    bronze.groupBy("resource_type").count().orderBy("resource_type").show(truncate=False)
    print("EOB Types")
    silver["claim_header"].groupBy("claim_type_code").count().orderBy("claim_type_code").show(truncate=False)
    print("Silver Results")
    for name in ["claim_header", "claim_line", "claim_line_financial", "claim_provider", "claim_diagnosis", "patient", "coverage"]:
        print(f"{name}: {silver[name].count()}")
    print("Quality")
    quality.where("failure_count > 0").select("check_name", "failure_count", "severity").show(truncate=False)
    print("Reconciliation")
    print(f"Bronze EOB count == claim_header count: {summary['bronze_eob_count_equals_claim_header_count']}")
    print(f"Header line sum: {summary['claim_header_line_count_sum']}")
    print(f"Claim line rows: {summary['claim_line_row_count']}")
    print("Ingestion Audit")
    audit.show(truncate=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest CMS Blue Button FHIR JSON to Bronze and Silver Spark tables.")
    parser.add_argument("--input", type=Path, default=ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "fhir_spark")
    parser.add_argument("--artifact-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--output-format", choices=["parquet", "delta"], default="parquet")
    parser.add_argument("--enable-delta", action="store_true")
    args = parser.parse_args()

    spark = create_spark_session(enable_delta=args.enable_delta)
    bronze = read_bronze_resources(spark, args.input)
    audit = build_ingestion_audit(bronze)
    silver = build_silver_tables(bronze)
    quality = build_data_quality_results(bronze, silver)
    silver["data_quality_results"] = quality
    summary = build_pipeline_summary(bronze, silver)

    bronze_base = args.output_root / "bronze"
    silver_base = args.output_root / "silver"
    write_dataframe(bronze, bronze_base / "fhir_resources", output_format=args.output_format)
    write_dataframe(audit, bronze_base / "ingestion_audit", output_format=args.output_format)
    write_silver_tables(silver, silver_base, output_format=args.output_format)
    _write_summary_artifacts(summary, quality, silver["claim_header"], args.artifact_root)
    _print_counts(bronze, audit, silver, quality, summary)
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
