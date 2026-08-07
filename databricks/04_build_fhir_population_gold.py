"""Build Phase 4 FHIR population-level Gold analytics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fhir.population_generator import write_population_bundle
from fhir.spark.bronze import (
    build_incremental_ingestion_audit,
    create_spark_session,
    deduplicate_bronze_resources,
    read_bronze_resources,
    write_dataframe,
)
from fhir.spark.gold import build_gold_tables, write_gold_csv_artifacts, write_gold_metric_artifacts, write_gold_tables
from fhir.spark.population import (
    timer,
    write_population_figures,
    write_population_findings_report,
    write_population_json_artifacts,
)
from fhir.spark.quality import build_data_quality_results, summarize_quality_results
from fhir.spark.silver import build_silver_tables, write_silver_tables


def _print_population_summary(manifest: dict, reconciliation: dict) -> None:
    print("FHIR Population Dataset")
    print(f"Beneficiaries: {manifest['beneficiary_count']}")
    print(f"Patients: {manifest['patient_resource_count']}")
    print(f"Coverage: {manifest['coverage_resource_count']}")
    print(f"EOBs: {manifest['eob_resource_count']}")
    print(f"Claim lines: {manifest['claim_line_count']}")
    print(f"Financial records: {manifest['financial_record_count']}")
    print("Claim types")
    for claim_type, count in sorted(manifest["claim_types"].items()):
        print(f"  {claim_type}: {count}")
    print("Reconciliation")
    for key, value in reconciliation.items():
        if key.endswith("reconciles"):
            print(f"  {key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase 4 FHIR population analytics.")
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "raw" / "fhir" / "population")
    parser.add_argument("--generate-fixture-population", action="store_true")
    parser.add_argument("--beneficiary-count", type=int, default=36)
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "fhir_spark_population")
    parser.add_argument("--artifact-root", type=Path, default=ROOT / "outputs")
    parser.add_argument("--report-path", type=Path, default=ROOT / "reports" / "fhir_interview_findings.md")
    parser.add_argument("--output-format", choices=["parquet", "delta"], default="parquet")
    parser.add_argument("--enable-delta", action="store_true")
    parser.add_argument("--high-cost-percentile", type=float, default=0.95)
    args = parser.parse_args()

    if args.generate_fixture_population or not any(args.input.glob("*.json")):
        write_population_bundle(args.input / "phase4_synthetic_population_bundle.json", args.beneficiary_count)

    started = timer()
    stage_runtimes: dict[str, float] = {}
    spark = create_spark_session("healthcare-fhir-population-gold", enable_delta=args.enable_delta)
    try:
        stage = timer()
        discovered_bronze = read_bronze_resources(
            spark,
            args.input,
            source_system="phase4_synthetic_fhir_population",
            ingestion_run_id="phase4-population",
        )
        bronze = deduplicate_bronze_resources(discovered_bronze)
        audit = build_incremental_ingestion_audit(discovered_bronze, bronze)
        stage_runtimes["bronze"] = timer() - stage

        stage = timer()
        silver = build_silver_tables(bronze)
        quality = build_data_quality_results(bronze, silver)
        silver["data_quality_results"] = quality
        stage_runtimes["silver"] = timer() - stage

        stage = timer()
        gold = build_gold_tables(bronze, silver, quality, high_cost_percentile=args.high_cost_percentile)
        stage_runtimes["gold"] = timer() - stage

        write_dataframe(bronze, args.output_root / "bronze" / "fhir_resources", output_format=args.output_format)
        write_dataframe(audit, args.output_root / "bronze" / "ingestion_audit", output_format=args.output_format)
        write_silver_tables(silver, args.output_root / "silver", output_format=args.output_format)
        write_gold_tables(gold, args.output_root / "gold", output_format=args.output_format)
        write_gold_csv_artifacts(gold, args.artifact_root)
        write_gold_metric_artifacts(bronze, silver, gold, args.artifact_root)
        summarize_quality_results(quality).coalesce(1).write.mode("overwrite").option("header", True).csv(
            str(args.artifact_root / "tables" / "silver_data_quality_summary.csv.tmp")
        )
        manifest, interview, reconciliation = write_population_json_artifacts(
            bronze,
            silver,
            gold,
            args.artifact_root,
            runtime_seconds=timer() - started,
            stage_runtimes=stage_runtimes,
        )
        write_population_figures(gold, silver, args.artifact_root / "figures" / "fhir_population")
        write_population_findings_report(gold, silver, bronze, interview, reconciliation, args.report_path)
        _print_population_summary(manifest, reconciliation)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
