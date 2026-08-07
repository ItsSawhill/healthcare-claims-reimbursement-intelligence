"""Build FHIR Gold reimbursement analytics from Bronze/Silver Spark transforms."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fhir.spark.bronze import build_ingestion_audit, create_spark_session, read_bronze_resources, write_dataframe
from fhir.spark.gold import (
    build_gold_tables,
    write_gold_csv_artifacts,
    write_gold_metric_artifacts,
    write_gold_tables,
    write_interview_findings,
)
from fhir.spark.quality import build_data_quality_results
from fhir.spark.silver import build_silver_tables, write_silver_tables


def _print_summary(bronze, silver, gold, summary, reconciliation) -> None:
    print("FHIR Resources")
    bronze.groupBy("resource_type").count().orderBy("resource_type").show(truncate=False)
    print("Gold Tables")
    for name, count in summary["gold_table_counts"].items():
        print(f"{name}: {count}")
    print("Claim Types")
    gold["claim_type_summary"].select(
        "claim_type_code",
        "claim_count",
        "claim_line_count",
        "financial_record_count",
        "total_submitted_amount",
        "total_provider_paid_amount",
        "total_covered_paid_amount",
        "total_drug_cost",
    ).show(truncate=False)
    print("High-Cost Claims")
    gold["high_cost_claims"].where("high_cost_flag = true").select(
        "eob_id",
        "claim_type_code",
        "cost_basis_name",
        "cost_basis_amount",
        "claim_type_percentile",
    ).show(truncate=False)
    print("Reconciliation")
    for key, value in reconciliation.items():
        print(f"{key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FHIR Gold reimbursement analytics.")
    parser.add_argument("--input", type=Path, default=ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "fhir_spark")
    parser.add_argument("--artifact-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--report-path", type=Path, default=ROOT / "reports" / "fhir_interview_findings.md")
    parser.add_argument("--output-format", choices=["parquet", "delta"], default="parquet")
    parser.add_argument("--enable-delta", action="store_true")
    parser.add_argument("--high-cost-percentile", type=float, default=0.95)
    args = parser.parse_args()

    spark = create_spark_session("healthcare-fhir-gold", enable_delta=args.enable_delta)
    bronze = read_bronze_resources(spark, args.input)
    audit = build_ingestion_audit(bronze)
    silver = build_silver_tables(bronze)
    quality = build_data_quality_results(bronze, silver)
    silver["data_quality_results"] = quality
    gold = build_gold_tables(bronze, silver, quality, high_cost_percentile=args.high_cost_percentile)

    write_dataframe(bronze, args.output_root / "bronze" / "fhir_resources", output_format=args.output_format)
    write_dataframe(audit, args.output_root / "bronze" / "ingestion_audit", output_format=args.output_format)
    write_silver_tables(silver, args.output_root / "silver", output_format=args.output_format)
    write_gold_tables(gold, args.output_root / "gold", output_format=args.output_format)
    write_gold_csv_artifacts(gold, args.artifact_root)
    summary, metrics, reconciliation = write_gold_metric_artifacts(bronze, silver, gold, args.artifact_root)
    write_interview_findings(gold, silver, bronze, metrics, reconciliation, args.report_path)
    _print_summary(bronze, silver, gold, summary, reconciliation)
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
