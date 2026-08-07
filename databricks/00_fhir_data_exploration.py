"""Local-first FHIR data exploration entry point.

This script can be run as regular Python against local JSON fixtures. It is
placed under databricks/ so it can later become the first Databricks notebook,
but it does not require Spark, a cluster, or a Databricks workspace.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fhir.field_profiler import (
    build_profile_summary,
    calculate_field_availability,
    count_eobs_by_type,
    discover_provider_references,
    extract_diagnoses,
    extract_financial_adjudications,
    extract_service_codings,
    identify_adjudication_category_codes,
    identify_service_date_range,
    profile_resources,
    summarize_financial_adjudications,
    unknown_financial_codes,
)
from fhir.resource_loader import FHIRLoadError, load_fhir_path


TABLE_DIR = ROOT / "outputs" / "tables"
METRICS_DIR = ROOT / "outputs" / "metrics"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(resources: list[dict]) -> None:
    profile = profile_resources(resources)
    eob_counts = count_eobs_by_type(resources)
    financial_rows = summarize_financial_adjudications(resources)
    availability = calculate_field_availability(resources)
    summary = build_profile_summary(resources)
    earliest, latest = identify_service_date_range(resources)
    financial_observations = extract_financial_adjudications(resources)
    service_codings = extract_service_codings(resources)
    diagnoses = extract_diagnoses(resources)
    provider_observations = discover_provider_references(resources)

    print("FHIR exploration summary")
    print("========================")
    print(f"Resource counts: {profile.resource_counts}")
    print(f"EOB count: {summary['eob_resource_count']}")
    print(f"EOB counts by type: {eob_counts}")
    print(f"Service-date coverage: {summary['service_date_min']} to {summary['service_date_max']}")
    print(f"Diagnosis coverage: {len(diagnoses)} diagnosis coding observations")
    print(f"HCPCS/service-code coverage: {len(service_codings)} service coding observations")
    print(f"Provider-reference coverage: {summary['percentage_eobs_with_provider_reference']:.1%} of EOBs")
    print(f"Financial-field coverage: {summary['percentage_eobs_with_financial_data']:.1%} of EOBs")
    print(f"Observed adjudication codes: {identify_adjudication_category_codes(resources)}")
    print(f"Unknown/unsupported financial codes: {unknown_financial_codes(resources)}")
    print(f"Earliest service date: {earliest}")
    print(f"Latest service date: {latest}")
    print("")
    print("Financial code summary")
    for row in financial_rows:
        print(
            "- {code}: {count} occurrences, {coverage:.1%} amount coverage, claim types {types}, status {status}".format(
                code=row["adjudication_code"],
                count=row["occurrence_count"],
                coverage=row["amount_coverage"],
                types=row["claim_types_observed"],
                status=row["mapping_status"],
            )
        )
    print("")
    print("Field availability by claim type")
    for row in availability:
        print(
            "- {eob_type} | {field}: {populated_count}/{resource_count} ({populated_percentage:.1%})".format(**row)
        )
    print("")
    print(f"Provider observations: {len(provider_observations)}")
    print(f"Financial observations: {len(financial_observations)}")


def main() -> int:
    """Profile one local FHIR resource or Bundle JSON file."""
    parser = argparse.ArgumentParser(description="Explore local FHIR JSON resources.")
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a FHIR JSON file or directory of Patient, Coverage, ExplanationOfBenefit, and Bundle JSON files.",
    )
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="Write outputs/tables/fhir_field_availability.csv and outputs/metrics/fhir_profile_summary.json.",
    )
    args = parser.parse_args()

    try:
        resources = load_fhir_path(args.path)
    except FHIRLoadError as exc:
        print(f"FHIR exploration failed: {exc}", file=sys.stderr)
        return 1

    _print_summary(resources)
    if args.write_artifacts:
        availability = calculate_field_availability(resources)
        summary = build_profile_summary(resources)
        _write_csv(TABLE_DIR / "fhir_field_availability.csv", availability)
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        (METRICS_DIR / "fhir_profile_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print("")
        print(f"Wrote {TABLE_DIR / 'fhir_field_availability.csv'}")
        print(f"Wrote {METRICS_DIR / 'fhir_profile_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
