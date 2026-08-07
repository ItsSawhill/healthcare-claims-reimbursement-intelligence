"""Population-level FHIR reimbursement artifacts and findings."""

from __future__ import annotations

import csv
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def _safe_date(value: Any) -> str | None:
    return value.isoformat() if value else None


def build_dataset_manifest(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    gold: dict[str, DataFrame],
    *,
    extraction_failures: int = 0,
) -> dict[str, Any]:
    """Build a provenance-aware dataset manifest from computed tables."""
    service_dates = silver["claim_header"].agg(F.min("service_start").alias("min_date"), F.max("service_end").alias("max_date")).first()
    provenance = {
        row["provenance_classification"] or "unclassified": row["count"]
        for row in bronze.groupBy("provenance_classification").count().collect()
    }
    service_systems = {
        row["service_code_system"] or "missing": row["count"]
        for row in silver["claim_line"].groupBy("service_code_system").count().collect()
    }
    claim_types = {
        row["claim_type_code"] or "missing": row["count"]
        for row in silver["claim_header"].groupBy("claim_type_code").count().collect()
    }
    duplicate_count = (
        bronze.where(F.col("valid_resource"))
        .groupBy("source_system", "source_dataset", "resource_type", "resource_id")
        .count()
        .where(F.col("count") > 1)
        .count()
    )
    return {
        "beneficiary_count": silver["patient"].select("patient_id").distinct().count(),
        "patient_resource_count": silver["patient"].count(),
        "coverage_resource_count": silver["coverage"].count(),
        "eob_resource_count": silver["claim_header"].count(),
        "claim_line_count": silver["claim_line"].count(),
        "diagnosis_count": silver["claim_diagnosis"].count(),
        "provider_count": silver["claim_provider"].count(),
        "financial_record_count": silver["claim_line_financial"].count(),
        "claim_types": claim_types,
        "service_code_systems": service_systems,
        "service_date_min": _safe_date(service_dates["min_date"]),
        "service_date_max": _safe_date(service_dates["max_date"]),
        "official_cms_resource_count": provenance.get("official_cms_synthetic", 0),
        "external_synthetic_resource_count": provenance.get("external_synthetic", 0),
        "documentation_fixture_resource_count": provenance.get("documentation_based_fixture", 0),
        "extraction_failures": extraction_failures,
        "duplicate_resource_count": duplicate_count,
        "provenance_summary": provenance,
        "gold_table_counts": {name: frame.count() for name, frame in gold.items()},
    }


def write_beneficiary_manifest(silver: dict[str, DataFrame], output_path: str | Path) -> None:
    """Write one beneficiary-level manifest CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = silver["claim_header"]
    line = silver["claim_line"]
    coverage = silver["coverage"]
    line_counts = line.groupBy("patient_id").agg(F.count("*").alias("claim_line_count"))
    claim_types = header.groupBy("patient_id").agg(
        F.count("*").alias("eob_count"),
        F.concat_ws("|", F.sort_array(F.collect_set("claim_type_code"))).alias("claim_types"),
        F.min("service_start").alias("service_date_min"),
        F.max("service_end").alias("service_date_max"),
    )
    cov = coverage.groupBy("patient_id").agg(
        F.count("*").alias("coverage_count"),
        F.first("source_dataset", ignorenulls=True).alias("source_dataset"),
        F.first("provenance_classification", ignorenulls=True).alias("source_type"),
    )
    rows = (
        silver["patient"]
        .select(F.col("patient_id").alias("beneficiary_alias"), F.col("patient_id"))
        .join(cov, "patient_id", "left")
        .join(claim_types, "patient_id", "left")
        .join(line_counts, "patient_id", "left")
        .select(
            "beneficiary_alias",
            F.lit(1).alias("patient_resource_count"),
            F.coalesce("coverage_count", F.lit(0)).alias("coverage_count"),
            F.coalesce("eob_count", F.lit(0)).alias("eob_count"),
            F.coalesce("claim_line_count", F.lit(0)).alias("claim_line_count"),
            "claim_types",
            "service_date_min",
            "service_date_max",
            "source_dataset",
            "source_type",
            F.lit("completed").alias("extraction_status"),
        )
        .orderBy("beneficiary_alias")
        .collect()
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "beneficiary_alias",
                "patient_resource_count",
                "coverage_count",
                "eob_count",
                "claim_line_count",
                "claim_types",
                "service_date_min",
                "service_date_max",
                "source_dataset",
                "source_type",
                "extraction_status",
            ],
        )
        writer.writeheader()
        for row in rows:
            item = row.asDict()
            item["service_date_min"] = _safe_date(item["service_date_min"])
            item["service_date_max"] = _safe_date(item["service_date_max"])
            writer.writerow(item)


def build_population_reconciliation(bronze: DataFrame, silver: dict[str, DataFrame], gold: dict[str, DataFrame]) -> dict[str, Any]:
    """Build Phase 4 reconciliation metrics."""
    bronze_patient = bronze.where((F.col("valid_resource")) & (F.col("resource_type") == "Patient")).count()
    bronze_eob = bronze.where((F.col("valid_resource")) & (F.col("resource_type") == "ExplanationOfBenefit")).count()
    silver_line_expected = silver["claim_header"].agg(F.sum("line_item_count").alias("count")).first()["count"] or 0
    financial_summary_count = gold["financial_component_summary"].agg(F.sum("record_count").alias("count")).first()["count"] or 0
    service_summary_count = gold["service_cost_summary"].agg(F.sum("service_count").alias("count")).first()["count"] or 0
    member_month_duplicates = gold["member_months"].groupBy("patient_id", "coverage_month", "coverage_type_code").count().where(F.col("count") > 1).count()
    concentration_total = gold["patient_spending_concentration"].agg(F.sum("total_cost_basis").alias("total")).first()["total"] or 0.0
    claim_cost_total = gold["high_cost_claims"].agg(F.sum("cost_basis_amount").alias("total")).first()["total"] or 0.0
    return {
        "bronze_patient_count": bronze_patient,
        "silver_patient_count": silver["patient"].count(),
        "bronze_patient_reconciles": bronze_patient == silver["patient"].count(),
        "bronze_eob_count": bronze_eob,
        "silver_claim_header_count": silver["claim_header"].count(),
        "bronze_eob_reconciles": bronze_eob == silver["claim_header"].count(),
        "claim_header_line_item_sum": int(silver_line_expected),
        "silver_claim_line_count": silver["claim_line"].count(),
        "claim_lines_reconcile": int(silver_line_expected) == silver["claim_line"].count(),
        "silver_financial_record_count": silver["claim_line_financial"].count(),
        "gold_financial_summary_record_count": int(financial_summary_count),
        "financial_records_reconcile": int(financial_summary_count) == silver["claim_line_financial"].count(),
        "gold_service_summary_count": int(service_summary_count),
        "service_counts_reconcile": int(service_summary_count) == silver["claim_line"].count(),
        "provider_attribution_rows": silver["claim_provider"].count(),
        "member_month_duplicate_patient_month_type_count": member_month_duplicates,
        "member_month_uniqueness_reconciles": member_month_duplicates == 0,
        "pmpm_months_with_denominator": gold["pmpm_summary"].where(F.col("member_months") > 0).count(),
        "patient_concentration_total_cost_basis": round(float(concentration_total), 2),
        "high_cost_claim_total_cost_basis": round(float(claim_cost_total), 2),
        "patient_concentration_reconciles": abs(float(concentration_total) - float(claim_cost_total)) < 0.01,
        "high_cost_claim_population_count": gold["high_cost_claims"].count(),
    }


def build_population_interview_metrics(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    gold: dict[str, DataFrame],
) -> dict[str, Any]:
    """Build compact population-level interview metrics from Gold tables."""
    concentration = gold["patient_spending_concentration"]
    utilization = gold["patient_utilization"]
    high_cost = gold["high_cost_claims"]
    quality = gold["fhir_data_quality_summary"]
    population_count = concentration.count()
    top_10 = concentration.where(F.col("top_10_pct_flag")).agg(F.max("cumulative_spend_share").alias("share")).first()["share"] or 0.0
    top_20 = concentration.where(F.col("top_20_pct_flag")).agg(F.max("cumulative_spend_share").alias("share")).first()["share"] or 0.0
    spend_stats = concentration.agg(
        F.avg("total_cost_basis").alias("mean"),
        F.expr("percentile_approx(total_cost_basis, 0.5)").alias("median"),
        F.expr("percentile_approx(total_cost_basis, 0.9)").alias("p90"),
        F.expr("percentile_approx(total_cost_basis, 0.95)").alias("p95"),
    ).first()
    util_stats = utilization.agg(
        F.avg("claim_count").alias("mean_claims"),
        F.expr("percentile_approx(claim_count, 0.5)").alias("median_claims"),
        F.expr("percentile_approx(claim_count, 0.9)").alias("p90_claims"),
        F.avg("claim_line_count").alias("mean_lines"),
        F.avg("unique_service_count").alias("mean_services"),
        F.avg("unique_provider_count").alias("mean_providers"),
    ).first()
    p90_claims = util_stats["p90_claims"] or 0
    high_util_count = utilization.where(F.col("claim_count") >= p90_claims).count()
    quality_rows = {
        row["metric_name"]: (row["numerator"], row["denominator"], row["percentage"])
        for row in quality.groupBy("metric_name").agg(
            F.sum("numerator").alias("numerator"),
            F.sum("denominator").alias("denominator"),
            F.when(F.sum("denominator") > 0, F.sum("numerator") / F.sum("denominator")).otherwise(F.lit(0.0)).alias("percentage"),
        ).collect()
    }
    high_cost_by_type = {
        row["claim_type_code"]: row["count"]
        for row in high_cost.where(F.col("high_cost_flag")).groupBy("claim_type_code").count().collect()
    }
    return {
        "resource_count": bronze.count(),
        "beneficiary_count": silver["patient"].count(),
        "eob_count": silver["claim_header"].count(),
        "claim_line_count": silver["claim_line"].count(),
        "diagnosis_count": silver["claim_diagnosis"].count(),
        "provider_count": silver["claim_provider"].count(),
        "financial_record_count": silver["claim_line_financial"].count(),
        "claim_types": {row["claim_type_code"]: row["count"] for row in silver["claim_header"].groupBy("claim_type_code").count().collect()},
        "unique_service_codes": silver["claim_line"].select("service_code").distinct().count(),
        "service_code_systems": {row["service_code_system"] or "missing": row["count"] for row in silver["claim_line"].groupBy("service_code_system").count().collect()},
        "mean_patient_cost_basis": float(spend_stats["mean"] or 0.0),
        "median_patient_cost_basis": float(spend_stats["median"] or 0.0),
        "p90_patient_cost_basis": float(spend_stats["p90"] or 0.0),
        "p95_patient_cost_basis": float(spend_stats["p95"] or 0.0),
        "top_10_spending_share": float(top_10),
        "top_20_spending_share": float(top_20),
        "mean_claims_per_beneficiary": float(util_stats["mean_claims"] or 0.0),
        "median_claims_per_beneficiary": float(util_stats["median_claims"] or 0.0),
        "p90_claims_per_beneficiary": float(p90_claims),
        "mean_claim_lines_per_beneficiary": float(util_stats["mean_lines"] or 0.0),
        "mean_unique_services_per_beneficiary": float(util_stats["mean_services"] or 0.0),
        "mean_unique_providers_per_beneficiary": float(util_stats["mean_providers"] or 0.0),
        "high_utilization_threshold": float(p90_claims),
        "high_utilization_patient_count": high_util_count,
        "high_utilization_patient_percentage": (high_util_count / population_count) if population_count else 0.0,
        "member_month_count": gold["member_months"].select("patient_id", "coverage_month").distinct().count(),
        "high_cost_claim_count": high_cost.where(F.col("high_cost_flag")).count(),
        "high_cost_claim_rate": high_cost.where(F.col("high_cost_flag")).count() / high_cost.count() if high_cost.count() else 0.0,
        "high_cost_claims_by_type": high_cost_by_type,
        "quality_metrics": quality_rows,
    }


def write_population_json_artifacts(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    gold: dict[str, DataFrame],
    output_root: str | Path,
    *,
    runtime_seconds: float,
    stage_runtimes: dict[str, float],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Write Phase 4 JSON and CSV manifest artifacts."""
    output_root = Path(output_root)
    metrics_dir = output_root / "metrics"
    tables_dir = output_root / "tables"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_dataset_manifest(bronze, silver, gold)
    interview = build_population_interview_metrics(bronze, silver, gold)
    reconciliation = build_population_reconciliation(bronze, silver, gold)
    performance = {
        "input_resource_count": manifest["patient_resource_count"] + manifest["coverage_resource_count"] + manifest["eob_resource_count"],
        "bronze_row_count": bronze.count(),
        "silver_row_counts": {name: frame.count() for name, frame in silver.items()},
        "gold_row_counts": {name: frame.count() for name, frame in gold.items()},
        "pipeline_runtime_seconds": round(runtime_seconds, 3),
        "major_stage_runtimes_seconds": {key: round(value, 3) for key, value in stage_runtimes.items()},
        "duplicate_resources_skipped": manifest["duplicate_resource_count"],
        "invalid_resources": bronze.where(~F.col("valid_resource")).count(),
        "reconciliation_status": all(value for key, value in reconciliation.items() if key.endswith("_reconciles")),
    }
    (metrics_dir / "fhir_dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "fhir_population_interview_metrics.json").write_text(json.dumps(interview, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "fhir_population_reconciliation.json").write_text(json.dumps(reconciliation, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "fhir_population_performance.json").write_text(json.dumps(performance, indent=2, sort_keys=True), encoding="utf-8")
    write_beneficiary_manifest(silver, tables_dir / "fhir_beneficiary_manifest.csv")
    return manifest, interview, reconciliation


def _save_bar(labels: list[str], values: list[float], title: str, ylabel: str, path: Path) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, values, color="#3b7ea1")
    ax.set_title(f"{title} (synthetic)")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _save_hist(values: list[float], title: str, xlabel: str, path: Path) -> None:
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(values, bins=min(15, max(5, int(math.sqrt(len(values) or 1)))), color="#6a994e", edgecolor="white")
    ax.set_title(f"{title} (synthetic)")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Beneficiaries")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_population_figures(gold: dict[str, DataFrame], silver: dict[str, DataFrame], output_dir: str | Path) -> None:
    """Write interview-quality population figures from aggregated outputs."""
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    claim_rows = gold["claim_type_summary"].orderBy("claim_type_code").collect()
    _save_bar([r["claim_type_code"] for r in claim_rows], [r["claim_count"] for r in claim_rows], "Claims by Type", "Claims", output / "claims_by_type.png")
    _save_bar([r["claim_type_code"] for r in claim_rows], [r["claim_line_count"] for r in claim_rows], "Claim Lines by Type", "Lines", output / "claim_lines_by_type.png")
    concentration = gold["patient_spending_concentration"].orderBy(F.col("total_cost_basis").desc()).collect()
    _save_hist([float(r["total_cost_basis"]) for r in concentration], "Patient Cost-Basis Distribution", "Claim-type-aware cost basis ($)", output / "patient_cost_basis_distribution.png")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(range(1, len(concentration) + 1), [float(r["cumulative_spend_share"]) for r in concentration], marker="o", linewidth=1)
    ax.set_title("Cumulative Patient Spending Concentration (synthetic)")
    ax.set_xlabel("Patients sorted by cost basis")
    ax.set_ylabel("Cumulative spend share")
    fig.tight_layout()
    fig.savefig(output / "cumulative_patient_spending_concentration.png", dpi=160)
    plt.close(fig)
    _save_hist([float(r["claim_count"]) for r in gold["patient_utilization"].collect()], "Claims per Patient Distribution", "Claims per beneficiary", output / "claims_per_patient_distribution.png")
    _save_hist([float(r["claim_count"]) for r in gold["provider_population_summary"].collect()], "Provider Volume Distribution", "Claims per provider", output / "provider_volume_distribution.png")
    top_services = gold["service_cost_summary"].orderBy(F.col("service_count").desc()).limit(10).collect()
    _save_bar([r["service_code"] for r in top_services], [r["service_count"] for r in top_services], "Top Service Codes", "Service lines", output / "top_service_codes.png")
    high_cost = gold["high_cost_claims"].where(F.col("high_cost_flag")).groupBy("claim_type_code").count().orderBy("claim_type_code").collect()
    _save_bar([r["claim_type_code"] for r in high_cost], [r["count"] for r in high_cost], "High-Cost Claims by Type", "Claims", output / "high_cost_claims_by_type.png")
    monthly = gold["monthly_reimbursement"].groupBy("service_month").agg(F.sum("claim_count").alias("claims")).orderBy("service_month").collect()
    _save_bar([_safe_date(r["service_month"]) for r in monthly], [r["claims"] for r in monthly], "Monthly Claim Volume", "Claims", output / "monthly_claim_volume.png")
    completeness = gold["fhir_data_quality_summary"].where(F.col("metric_name").isin("claim lines with service codes", "claim lines with any financial data")).collect()
    _save_bar([f"{r['claim_type_code']} {r['metric_name'][:11]}" for r in completeness], [float(r["percentage"]) for r in completeness], "FHIR Field Completeness by Claim Type", "Completeness", output / "fhir_field_completeness_by_claim_type.png")
    systems = silver["claim_line"].groupBy("service_code_system").count().collect()
    _save_bar([r["service_code_system"].split("/")[-1] if r["service_code_system"] else "missing" for r in systems], [r["count"] for r in systems], "Service-Code System Distribution", "Claim lines", output / "service_code_system_distribution.png")
    pmpm = gold["pmpm_summary"].groupBy("claim_type_code").agg(F.avg("pmpm_drug_cost").alias("drug"), F.avg("pmpm_provider_paid").alias("provider"), F.avg("pmpm_covered_paid").alias("covered")).collect()
    _save_bar([r["claim_type_code"] for r in pmpm], [float(r["drug"] or r["provider"] or r["covered"] or 0.0) for r in pmpm], "PMPM by Claim Type", "Monthly amount per member ($)", output / "pmpm_by_claim_type.png")


def write_population_findings_report(
    gold: dict[str, DataFrame],
    silver: dict[str, DataFrame],
    bronze: DataFrame,
    metrics: dict[str, Any],
    reconciliation: dict[str, Any],
    report_path: str | Path,
) -> None:
    """Write Phase 4 interview findings with computed values only."""
    report_path = Path(report_path)
    claim_mix = "\n".join([f"- `{k}`: {v} claims" for k, v in sorted(metrics["claim_types"].items())])
    service_mix = "\n".join([f"- `{k}`: {v} claim lines" for k, v in sorted(metrics["service_code_systems"].items())])
    high_cost = metrics["high_cost_claims_by_type"]
    top_10_pct = metrics["top_10_spending_share"] * 100
    top_20_pct = metrics["top_20_spending_share"] * 100
    supported_financial = silver["claim_line_financial"].where(F.col("mapping_status") != "unsupported").count()
    financial_count = silver["claim_line_financial"].count()
    provider_count = gold["provider_population_summary"].count()
    pmpm_rows = gold["pmpm_summary"].orderBy("service_month", "claim_type_code").limit(12).collect()
    pmpm_lines = "\n".join(
        [
            f"- {r['service_month']} `{r['claim_type_code']}`: members {r['member_months']}, drug PMPM {r['pmpm_drug_cost']}, provider-paid PMPM {r['pmpm_provider_paid']}, covered-paid PMPM {r['pmpm_covered_paid']}"
            for r in pmpm_rows
        ]
    )
    top_findings = [
        f"1. Across {metrics['beneficiary_count']} synthetic beneficiaries, the top 10% accounted for {top_10_pct:.1f}% of the selected claim-type-aware cost basis. Source Gold table: patient_spending_concentration.",
        f"2. The top 20% accounted for {top_20_pct:.1f}% of selected cost basis, showing concentration within this synthetic cohort only. Source Gold table: patient_spending_concentration.",
        f"3. The cohort contains {metrics['eob_count']} EOBs and {metrics['claim_line_count']} claim lines across {len(metrics['claim_types'])} claim types. Source Gold table: claim_type_summary.",
        f"4. Service vocabularies remain separate: {metrics['service_code_systems']}. Source Gold table: service_cost_summary.",
        f"5. {supported_financial}/{financial_count} financial adjudication records have supported or candidate mappings. Source Gold table: financial_component_summary.",
        f"6. {metrics['high_cost_claim_count']}/{metrics['eob_count']} claims are flagged high-cost using within-type percentiles, not anomaly labels. Source Gold table: high_cost_claims.",
        f"7. Mean claims per beneficiary is {metrics['mean_claims_per_beneficiary']:.2f}; high utilization is defined at the p90 threshold of {metrics['p90_claims_per_beneficiary']:.0f} claims. Source Gold table: patient_utilization.",
        f"8. Provider population analytics cover {provider_count} provider-role/source groups with double-count protected financial attribution. Source Gold table: provider_population_summary.",
        f"9. Member-month denominators include {metrics['member_month_count']} unique active beneficiary months. Source Gold table: member_months.",
        f"10. Provider attribution and service-code completeness are reported by claim type to show FHIR heterogeneity. Source Gold table: fhir_data_quality_summary.",
    ]
    text = f"""# FHIR Interview Findings

## Population-Level Findings

### Dataset Scale

- Beneficiaries: {metrics['beneficiary_count']}
- Bronze resources: {metrics['resource_count']}
- EOBs: {metrics['eob_count']}
- Claim lines: {metrics['claim_line_count']}
- Diagnoses: {metrics['diagnosis_count']}
- Provider records: {metrics['provider_count']}
- Financial records: {metrics['financial_record_count']}
- Unique service codes: {metrics['unique_service_codes']}
- Claim types:
{claim_mix}
- Service-code systems:
{service_mix}

The population bundle is synthetic. It combines resources adapted from the official CMS Blue Button synthetic sample with documentation-based claim-shape fixtures. It should not be interpreted as real Medicare utilization or spending.

### Spending Concentration

- Mean patient cost basis: ${metrics['mean_patient_cost_basis']:,.2f}
- Median patient cost basis: ${metrics['median_patient_cost_basis']:,.2f}
- P90 patient cost basis: ${metrics['p90_patient_cost_basis']:,.2f}
- P95 patient cost basis: ${metrics['p95_patient_cost_basis']:,.2f}
- Top 10% spending share: {top_10_pct:.1f}%
- Top 20% spending share: {top_20_pct:.1f}%

Within this synthetic cohort of {metrics['beneficiary_count']} beneficiaries, the top 10% accounted for {top_10_pct:.1f}% of the selected claim-type-aware cost basis. This describes the synthetic cohort and should not be interpreted as an estimate of Medicare population spending.

### Utilization

- Mean claims per beneficiary: {metrics['mean_claims_per_beneficiary']:.2f}
- Median claims per beneficiary: {metrics['median_claims_per_beneficiary']:.2f}
- P90 claims per beneficiary: {metrics['p90_claims_per_beneficiary']:.2f}
- High-utilization threshold: {metrics['high_utilization_threshold']:.2f} claims
- High-utilization beneficiaries: {metrics['high_utilization_patient_count']} ({metrics['high_utilization_patient_percentage']:.1%})
- Mean unique services per beneficiary: {metrics['mean_unique_services_per_beneficiary']:.2f}

High utilization is descriptive only. It is not labeled waste, abuse, fraud, or unnecessary care.

### PMPM

PMPM uses distinct active beneficiary-months from Coverage and keeps claim-type-specific numerators separate.

{pmpm_lines}

No universal paid PMPM is created because professional, institutional, and Part D payment concepts are not interchangeable.

### Providers

- Provider population groups: {provider_count}
- Mean unique providers per beneficiary: {metrics['mean_unique_providers_per_beneficiary']:.2f}

Provider financial attribution is reported only where a claim has one provider attribution. Multi-provider claims contribute activity and volume but do not multiply dollars.

### Claim Mix

{claim_mix}

### High-Cost Claims

- High-cost claim count: {metrics['high_cost_claim_count']}
- High-cost claim rate: {metrics['high_cost_claim_rate']:.1%}
- High-cost claims by type: {high_cost}

High-cost flags use within-claim-type percentiles and are not fraud or anomaly labels.

### FHIR Interoperability

- Financial mapping coverage: {supported_financial}/{financial_count} records ({(supported_financial / financial_count if financial_count else 0):.1%})
- Quality metrics include numerator, denominator, and percentage by claim type in `fhir_data_quality_summary`.

### Engineering Findings

- Heterogeneous EOB shapes require typed financial components.
- Bronze preserves raw FHIR JSON and provenance.
- Silver normalizes patients, coverage, claims, lines, diagnoses, providers, and adjudication records.
- Gold adds semantic reimbursement tables, member months, PMPM, concentration, and provider population analytics.
- Unknown adjudication codes remain auditable.
- Spark reconciliation checks protect Bronze/Silver/Gold consistency.

### Top 10 Interview Findings

{chr(10).join(top_findings)}

### Reconciliation

```json
{json.dumps(reconciliation, indent=2, sort_keys=True)}
```

### Limitations

- Automated CMS sandbox multi-beneficiary extraction requires OAuth credentials and was not run here.
- The generated population is adapted from synthetic templates; it is not a downloaded CMS population export.
- Carrier and Outpatient population records are documentation-based structural fixtures and are excluded from claims of official CMS population representativeness.
- Synthetic dates, providers, and amounts support engineering demonstration, not actuarial conclusions.
- The dataset is useful for pipeline and analytics design, but it is still not sufficient for credible ML anomaly modeling.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")


def timer() -> float:
    """Return a monotonic timestamp for basic stage timing."""
    return time.perf_counter()
