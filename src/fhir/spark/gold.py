"""FHIR Gold reimbursement analytics built from Silver tables."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import Window
from pyspark.sql import functions as F

from .metrics import CLAIM_TYPE_COST_BASIS, FINANCIAL_AMOUNT_COLUMNS, PDE_ANALYTICAL_CATEGORIES
from .reconciliation import build_gold_reconciliation


def _sum_col(column: str) -> F.Column:
    return F.coalesce(F.sum(F.col(column)), F.lit(0.0)).alias(f"total_{column}")


def _silver_base(silver: dict[str, DataFrame]) -> DataFrame:
    return silver["claim_line"].join(
        silver["claim_header"].select("eob_id", "service_start", "service_end", "line_item_count", "diagnosis_count"),
        "eob_id",
        "left",
    )


def _pde_financial_by_line(silver: dict[str, DataFrame]) -> DataFrame:
    financial = silver["claim_line_financial"]
    rows = financial.groupBy("eob_id", "line_number").agg(
        *[
            F.sum(F.when(F.col("analytical_category") == category, F.col("amount"))).alias(output_name)
            for category, output_name in PDE_ANALYTICAL_CATEGORIES.items()
        ]
    )
    return rows


def _line_enriched(silver: dict[str, DataFrame]) -> DataFrame:
    return _silver_base(silver).join(_pde_financial_by_line(silver), ["eob_id", "line_number"], "left")


def build_claim_type_summary(silver: dict[str, DataFrame]) -> DataFrame:
    """Build claim-type-level reimbursement summary without combining payment concepts."""
    line = _line_enriched(silver)
    financial_counts = silver["claim_line_financial"].groupBy("claim_type_code").agg(F.count("*").alias("financial_record_count"))
    provider_counts = silver["claim_provider"].groupBy("claim_type_code", "eob_id") if "claim_type_code" in silver["claim_provider"].columns else None
    providers = silver["claim_provider"].join(
        silver["claim_header"].select("eob_id", "claim_type_code"),
        "eob_id",
        "left",
    )
    provider_by_type = providers.groupBy("claim_type_code").agg(
        F.countDistinct(F.coalesce("provider_identifier", "provider_reference")).alias("unique_provider_count")
    )
    grouped = line.groupBy("claim_type_code").agg(
        F.countDistinct("eob_id").alias("claim_count"),
        F.count("*").alias("claim_line_count"),
        F.countDistinct("patient_id").alias("unique_patient_count"),
        F.min("service_date").alias("service_date_min"),
        F.max("service_date").alias("service_date_max"),
        _sum_col("submitted_amount"),
        _sum_col("allowed_amount"),
        _sum_col("provider_paid_amount"),
        _sum_col("covered_paid_amount"),
        _sum_col("beneficiary_paid_amount"),
        _sum_col("deductible_amount"),
        _sum_col("coinsurance_amount"),
        _sum_col("noncovered_amount"),
        F.avg("submitted_amount").alias("avg_submitted_per_line"),
        F.avg("allowed_amount").alias("avg_allowed_per_line"),
        F.avg("provider_paid_amount").alias("avg_provider_paid_per_line"),
        F.avg("covered_paid_amount").alias("avg_covered_paid_per_line"),
        F.coalesce(F.sum("total_part_d_plan_paid"), F.lit(0.0)).alias("total_part_d_plan_paid"),
        F.coalesce(F.sum("total_part_d_patient_paid"), F.lit(0.0)).alias("total_part_d_patient_paid"),
        F.coalesce(F.sum("total_drug_cost"), F.lit(0.0)).alias("total_drug_cost"),
    )
    return (
        grouped.join(provider_by_type, "claim_type_code", "left")
        .join(financial_counts, "claim_type_code", "left")
        .select(
            "claim_type_code",
            "claim_count",
            "claim_line_count",
            "unique_patient_count",
            F.coalesce("unique_provider_count", F.lit(0)).alias("unique_provider_count"),
            "service_date_min",
            "service_date_max",
            "total_submitted_amount",
            "total_allowed_amount",
            "total_provider_paid_amount",
            "total_covered_paid_amount",
            "total_beneficiary_paid_amount",
            "total_deductible_amount",
            "total_coinsurance_amount",
            "total_noncovered_amount",
            "avg_submitted_per_line",
            "avg_allowed_per_line",
            "avg_provider_paid_per_line",
            "avg_covered_paid_per_line",
            F.coalesce("financial_record_count", F.lit(0)).alias("financial_record_count"),
            "total_part_d_plan_paid",
            "total_part_d_patient_paid",
            "total_drug_cost",
        )
    )


def build_financial_component_summary(silver: dict[str, DataFrame]) -> DataFrame:
    """Summarize every financial adjudication component."""
    financial = silver["claim_line_financial"]
    return financial.groupBy(
        "claim_type_code",
        "analytical_category",
        "adjudication_code",
        "adjudication_display",
    ).agg(
        F.count("*").alias("record_count"),
        F.countDistinct("eob_id").alias("claim_count"),
        F.countDistinct(F.struct("eob_id", "line_number")).alias("claim_line_count"),
        F.coalesce(F.sum("amount"), F.lit(0.0)).alias("total_amount"),
        F.avg("amount").alias("avg_amount"),
        F.expr("percentile_approx(amount, 0.5)").alias("median_amount"),
        F.min("amount").alias("min_amount"),
        F.max("amount").alias("max_amount"),
    )


def build_service_cost_summary(silver: dict[str, DataFrame]) -> DataFrame:
    """Build service/procedure cost summary while preserving code systems."""
    line = _line_enriched(silver)
    provider_by_claim = silver["claim_provider"].groupBy("eob_id").agg(
        F.countDistinct(F.coalesce("provider_identifier", "provider_reference")).alias("provider_count")
    )
    line = line.join(provider_by_claim, "eob_id", "left")
    return line.groupBy("claim_type_code", "service_code_system", "service_code", "service_display").agg(
        F.count("*").alias("service_count"),
        F.countDistinct("eob_id").alias("claim_count"),
        F.countDistinct("patient_id").alias("patient_count"),
        F.coalesce(F.sum("provider_count"), F.lit(0)).alias("provider_count"),
        _sum_col("submitted_amount"),
        _sum_col("allowed_amount"),
        _sum_col("provider_paid_amount"),
        _sum_col("covered_paid_amount"),
        _sum_col("beneficiary_paid_amount"),
        F.avg("submitted_amount").alias("avg_submitted_amount"),
        F.avg("allowed_amount").alias("avg_allowed_amount"),
        F.avg("provider_paid_amount").alias("avg_provider_paid_amount"),
        F.avg("covered_paid_amount").alias("avg_covered_paid_amount"),
        F.coalesce(F.sum("total_part_d_plan_paid"), F.lit(0.0)).alias("total_part_d_plan_paid"),
        F.coalesce(F.sum("total_part_d_patient_paid"), F.lit(0.0)).alias("total_part_d_patient_paid"),
        F.coalesce(F.sum("total_drug_cost"), F.lit(0.0)).alias("total_drug_cost"),
    )


def build_provider_reimbursement(silver: dict[str, DataFrame]) -> DataFrame:
    """Build provider activity and safely attributed reimbursement summary."""
    providers = silver["claim_provider"]
    line = _line_enriched(silver)
    provider_counts = providers.groupBy("eob_id").agg(F.count("*").alias("provider_rows_for_eob"))
    provider_line = providers.join(provider_counts, "eob_id", "left").join(line, ["eob_id", "patient_id"], "left")
    safe = provider_line.withColumn("safe_to_allocate_money", F.col("provider_rows_for_eob") == F.lit(1))
    return safe.groupBy(
        "provider_identifier",
        "provider_reference",
        "provider_role_code",
        "provider_role_display",
        "provider_source",
        "claim_type_code",
    ).agg(
        F.countDistinct("eob_id").alias("claim_count"),
        F.countDistinct(F.struct("eob_id", "line_number")).alias("claim_line_count"),
        F.countDistinct("patient_id").alias("patient_count"),
        F.countDistinct("service_code").alias("service_count"),
        F.coalesce(F.sum(F.when(F.col("safe_to_allocate_money"), F.col("submitted_amount"))), F.lit(0.0)).alias("total_submitted_amount"),
        F.coalesce(F.sum(F.when(F.col("safe_to_allocate_money"), F.col("allowed_amount"))), F.lit(0.0)).alias("total_allowed_amount"),
        F.coalesce(F.sum(F.when(F.col("safe_to_allocate_money"), F.col("provider_paid_amount"))), F.lit(0.0)).alias("total_provider_paid_amount"),
        F.coalesce(F.sum(F.when(F.col("safe_to_allocate_money"), F.col("covered_paid_amount"))), F.lit(0.0)).alias("total_covered_paid_amount"),
        F.avg(F.when(F.col("safe_to_allocate_money"), F.col("provider_paid_amount"))).alias("avg_provider_paid_amount"),
        F.avg(F.when(F.col("safe_to_allocate_money"), F.col("covered_paid_amount"))).alias("avg_covered_paid_amount"),
    )


def build_patient_utilization(silver: dict[str, DataFrame]) -> DataFrame:
    """Build patient-level utilization summary."""
    line = _line_enriched(silver)
    providers = silver["claim_provider"].groupBy("patient_id").agg(
        F.countDistinct(F.coalesce("provider_identifier", "provider_reference")).alias("unique_provider_count")
    )
    grouped = line.groupBy("patient_id").agg(
        F.countDistinct("eob_id").alias("claim_count"),
        F.count("*").alias("claim_line_count"),
        F.countDistinct("claim_type_code").alias("claim_type_count"),
        F.countDistinct("service_code").alias("unique_service_count"),
        F.countDistinct(F.date_trunc("month", "service_date")).alias("service_month_count"),
        F.min("service_date").alias("service_date_min"),
        F.max("service_date").alias("service_date_max"),
        _sum_col("submitted_amount"),
        _sum_col("allowed_amount"),
        _sum_col("provider_paid_amount"),
        _sum_col("covered_paid_amount"),
        _sum_col("beneficiary_paid_amount"),
    )
    return grouped.join(providers, "patient_id", "left")


def build_monthly_reimbursement(silver: dict[str, DataFrame]) -> DataFrame:
    """Build sparse monthly reimbursement summary without trend claims."""
    line = _line_enriched(silver).withColumn("service_month", F.date_trunc("month", F.col("service_date")).cast("date"))
    return line.groupBy("service_month", "claim_type_code").agg(
        F.countDistinct("eob_id").alias("claim_count"),
        F.count("*").alias("claim_line_count"),
        F.countDistinct("service_code").alias("unique_service_count"),
        _sum_col("submitted_amount"),
        _sum_col("allowed_amount"),
        _sum_col("provider_paid_amount"),
        _sum_col("covered_paid_amount"),
        _sum_col("beneficiary_paid_amount"),
        F.coalesce(F.sum("total_part_d_plan_paid"), F.lit(0.0)).alias("total_part_d_plan_paid"),
        F.coalesce(F.sum("total_part_d_patient_paid"), F.lit(0.0)).alias("total_part_d_patient_paid"),
    )


def _claim_cost_basis(silver: dict[str, DataFrame]) -> DataFrame:
    line = _line_enriched(silver)
    pde_presence = silver["claim_line_financial"].groupBy("eob_id").agg(
        F.sum((F.col("analytical_category") == "part_d_total_drug_cost").cast("int")).alias("part_d_total_drug_cost_records"),
        F.sum((F.col("analytical_category") == "part_d_plan_paid_amount").cast("int")).alias("part_d_plan_paid_records"),
    )
    claim = line.groupBy("eob_id", "patient_id", "claim_type_code").agg(
        F.coalesce(F.sum("provider_paid_amount"), F.lit(0.0)).alias("provider_paid_amount"),
        F.coalesce(F.sum("allowed_amount"), F.lit(0.0)).alias("allowed_amount"),
        F.coalesce(F.sum("covered_paid_amount"), F.lit(0.0)).alias("covered_paid_amount"),
        F.coalesce(F.sum("total_drug_cost"), F.lit(0.0)).alias("part_d_total_drug_cost"),
        F.coalesce(F.sum("total_part_d_plan_paid"), F.lit(0.0)).alias("part_d_plan_paid_amount"),
    ).join(pde_presence, "eob_id", "left")
    return claim.withColumn(
        "cost_basis_name",
        F.when(F.col("claim_type_code") == "CARRIER", F.when(F.col("provider_paid_amount") > 0, F.lit("provider_paid_amount")).otherwise(F.lit("allowed_amount")))
        .when(F.col("claim_type_code") == "OUTPATIENT", F.when(F.col("covered_paid_amount") > 0, F.lit("covered_paid_amount")).otherwise(F.lit("allowed_amount")))
        .when(
            F.col("claim_type_code") == "PDE",
            F.when(F.col("part_d_total_drug_cost_records") > 0, F.lit("part_d_total_drug_cost")).otherwise(F.lit("part_d_plan_paid_amount")),
        )
        .otherwise(F.lit("unsupported")),
    ).withColumn(
        "cost_basis_amount",
        F.when(F.col("cost_basis_name") == "provider_paid_amount", F.col("provider_paid_amount"))
        .when(F.col("cost_basis_name") == "allowed_amount", F.col("allowed_amount"))
        .when(F.col("cost_basis_name") == "covered_paid_amount", F.col("covered_paid_amount"))
        .when(F.col("cost_basis_name") == "part_d_total_drug_cost", F.col("part_d_total_drug_cost"))
        .when(F.col("cost_basis_name") == "part_d_plan_paid_amount", F.col("part_d_plan_paid_amount")),
    )


def build_high_cost_claims(silver: dict[str, DataFrame], percentile_threshold: float = 0.95) -> DataFrame:
    """Build claim-type-aware high-cost flags using within-type percentiles."""
    costs = _claim_cost_basis(silver)
    within_type = Window.partitionBy("claim_type_code").orderBy(F.col("cost_basis_amount").asc())
    overall_comparable = Window.partitionBy("cost_basis_name").orderBy(F.col("cost_basis_amount").asc())
    return costs.withColumn("claim_type_percentile", F.cume_dist().over(within_type)).withColumn(
        "overall_percentile_if_comparable",
        F.cume_dist().over(overall_comparable),
    ).withColumn("high_cost_flag", F.col("claim_type_percentile") >= F.lit(percentile_threshold)).select(
        "eob_id",
        "patient_id",
        "claim_type_code",
        "cost_basis_name",
        "cost_basis_amount",
        "claim_type_percentile",
        "overall_percentile_if_comparable",
        "high_cost_flag",
    )


def build_fhir_data_quality_summary(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    quality_results: DataFrame,
) -> DataFrame:
    """Build interview-ready FHIR quality metrics by resource/claim type."""
    spark = bronze.sparkSession
    header = silver["claim_header"]
    line = silver["claim_line"]
    financial = silver["claim_line_financial"]
    provider_eobs = silver["claim_provider"].select("eob_id").distinct()
    financial_lines = financial.select("eob_id", "line_number").distinct()

    rows = []
    for row in header.groupBy("claim_type_code").agg(
        F.count("*").alias("denominator"),
        F.sum(F.col("patient_id").isNotNull().cast("int")).alias("patient_refs"),
        F.sum((F.col("diagnosis_count") > 0).cast("int")).alias("diagnosis"),
        F.sum((F.col("service_end") >= F.col("service_start")).cast("int")).alias("valid_period"),
    ).collect():
        claim_type = row["claim_type_code"]
        denominator = row["denominator"]
        rows.extend(
            [
                ("ExplanationOfBenefit", claim_type, "EOBs with patient reference", row["patient_refs"], denominator),
                ("ExplanationOfBenefit", claim_type, "EOBs with diagnoses", row["diagnosis"], denominator),
                ("ExplanationOfBenefit", claim_type, "valid service period rate", row["valid_period"], denominator),
            ]
        )
    provider_eobs = provider_eobs.withColumn("has_provider_attribution", F.lit(1))
    for row in header.join(provider_eobs, "eob_id", "left").groupBy("claim_type_code").agg(
        F.count("*").alias("denominator"),
        F.sum(F.coalesce(F.col("has_provider_attribution"), F.lit(0))).alias("provider_count"),
    ).collect():
        rows.append(("ExplanationOfBenefit", row["claim_type_code"], "EOBs with provider attribution", row["provider_count"], row["denominator"]))

    financial_lines = financial_lines.withColumn("has_financial_data", F.lit(1))
    line_metrics = line.join(financial_lines, ["eob_id", "line_number"], "left").groupBy("claim_type_code").agg(
        F.count("*").alias("denominator"),
        F.sum(F.col("service_code").isNotNull().cast("int")).alias("service_code"),
        F.sum(F.coalesce(F.col("has_financial_data"), F.lit(0))).alias("any_financial"),
        F.sum(F.col("submitted_amount").isNotNull().cast("int")).alias("submitted"),
        F.sum(F.col("allowed_amount").isNotNull().cast("int")).alias("allowed"),
        F.sum(F.col("provider_paid_amount").isNotNull().cast("int")).alias("provider_paid"),
        F.sum(F.col("covered_paid_amount").isNotNull().cast("int")).alias("covered_paid"),
    )
    for row in line_metrics.collect():
        claim_type = row["claim_type_code"]
        denominator = row["denominator"]
        rows.extend(
            [
                ("ExplanationOfBenefit.item", claim_type, "claim lines with service codes", row["service_code"], denominator),
                ("ExplanationOfBenefit.item", claim_type, "claim lines with any financial data", row["any_financial"], denominator),
                ("ExplanationOfBenefit.item", claim_type, "claim lines with submitted amount", row["submitted"], denominator),
                ("ExplanationOfBenefit.item", claim_type, "claim lines with allowed amount", row["allowed"], denominator),
                ("ExplanationOfBenefit.item", claim_type, "claim lines with provider paid amount", row["provider_paid"], denominator),
                ("ExplanationOfBenefit.item", claim_type, "claim lines with covered paid amount", row["covered_paid"], denominator),
            ]
        )
    unsupported = financial.groupBy("claim_type_code").agg(
        F.count("*").alias("denominator"),
        F.sum((F.col("mapping_status") == "unsupported").cast("int")).alias("unsupported"),
    )
    for row in unsupported.collect():
        rows.append(("ExplanationOfBenefit.item.adjudication", row["claim_type_code"], "unsupported financial code rate", row["unsupported"], row["denominator"]))

    duplicate_failures = quality_results.where(F.col("check_name").isin("duplicate_patient_ids", "duplicate_coverage_ids", "duplicate_eob_ids")).agg(
        F.sum("failure_count").alias("failures"),
        F.sum("record_count").alias("records"),
    ).first()
    rows.append(("FHIR resources", "ALL", "duplicate resource rate", duplicate_failures["failures"] or 0, duplicate_failures["records"] or 0))

    return spark.createDataFrame(rows, ["resource_type", "claim_type_code", "metric_name", "numerator", "denominator"]).withColumn(
        "percentage",
        F.when(F.col("denominator") > 0, F.col("numerator") / F.col("denominator")).otherwise(F.lit(0.0)),
    )


def build_gold_tables(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    quality_results: DataFrame,
    *,
    high_cost_percentile: float = 0.95,
) -> dict[str, DataFrame]:
    """Build all Gold FHIR reimbursement analytics tables."""
    gold = {
        "claim_type_summary": build_claim_type_summary(silver),
        "financial_component_summary": build_financial_component_summary(silver),
        "service_cost_summary": build_service_cost_summary(silver),
        "provider_reimbursement": build_provider_reimbursement(silver),
        "patient_utilization": build_patient_utilization(silver),
        "monthly_reimbursement": build_monthly_reimbursement(silver),
        "high_cost_claims": build_high_cost_claims(silver, high_cost_percentile),
    }
    gold["fhir_data_quality_summary"] = build_fhir_data_quality_summary(bronze, silver, quality_results)
    return gold


def write_gold_tables(gold: dict[str, DataFrame], base_path: str | Path, *, output_format: str = "parquet") -> None:
    """Write Gold tables to a local or Databricks path."""
    for name, frame in gold.items():
        frame.write.mode("overwrite").format(output_format).save(str(Path(base_path) / name))


def _single_csv_from_spark_dir(tmp_dir: Path, target: Path) -> None:
    part_files = sorted(tmp_dir.glob("part-*.csv"))
    if not part_files:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(part_files[0], target)
    shutil.rmtree(tmp_dir)


def write_gold_csv_artifacts(gold: dict[str, DataFrame], output_root: str | Path) -> None:
    """Write one CSV artifact per requested Gold output table."""
    output_root = Path(output_root)
    tables_dir = output_root / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "claim_type_summary": "fhir_claim_type_summary.csv",
        "service_cost_summary": "fhir_service_cost_summary.csv",
        "patient_utilization": "fhir_patient_utilization.csv",
        "provider_reimbursement": "fhir_provider_reimbursement.csv",
        "monthly_reimbursement": "fhir_monthly_reimbursement.csv",
        "financial_component_summary": "fhir_financial_component_summary.csv",
        "high_cost_claims": "fhir_high_cost_claims.csv",
        "fhir_data_quality_summary": "fhir_data_quality_summary.csv",
    }
    for table_name, filename in names.items():
        tmp_dir = tables_dir / f"{filename}.tmp"
        gold[table_name].coalesce(1).write.mode("overwrite").option("header", True).csv(str(tmp_dir))
        _single_csv_from_spark_dir(tmp_dir, tables_dir / filename)


def build_gold_pipeline_summary(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    gold: dict[str, DataFrame],
) -> dict[str, Any]:
    """Compute top-level Gold pipeline metrics."""
    high_cost = gold["high_cost_claims"]
    service = gold["service_cost_summary"]
    financial = gold["financial_component_summary"]
    service_systems = {
        row["service_code_system"]: row["service_count"]
        for row in service.groupBy("service_code_system").agg(F.sum("service_count").alias("service_count")).collect()
    }
    return {
        "gold_table_counts": {name: frame.count() for name, frame in gold.items()},
        "resource_count": bronze.count(),
        "eob_count": silver["claim_header"].count(),
        "claim_line_count": silver["claim_line"].count(),
        "provider_count": silver["claim_provider"].count(),
        "financial_record_count": silver["claim_line_financial"].count(),
        "claim_types": {row["claim_type_code"]: row["claim_count"] for row in gold["claim_type_summary"].select("claim_type_code", "claim_count").collect()},
        "service_date_min": gold["claim_type_summary"].agg(F.min("service_date_min")).first()[0].isoformat(),
        "service_date_max": gold["claim_type_summary"].agg(F.max("service_date_max")).first()[0].isoformat(),
        "unique_service_codes": service.select("service_code").where(F.col("service_code").isNotNull()).distinct().count(),
        "service_code_systems": service_systems,
        "high_cost_claim_count": high_cost.where(F.col("high_cost_flag")).count(),
        "unsupported_financial_code_count": silver["claim_line_financial"].where(F.col("mapping_status") == "unsupported").count(),
        "financial_component_count": financial.count(),
    }


def build_interview_metrics(gold: dict[str, DataFrame], silver: dict[str, DataFrame], bronze: DataFrame) -> dict[str, Any]:
    """Build compact metrics for interview/reporting use."""
    quality = gold["fhir_data_quality_summary"]
    claim_type_summary = gold["claim_type_summary"]
    service = gold["service_cost_summary"]

    def pct(metric_name: str) -> float:
        row = quality.where(F.col("metric_name") == metric_name).agg(F.sum("numerator").alias("num"), F.sum("denominator").alias("den")).first()
        return float(row["num"] / row["den"]) if row["den"] else 0.0

    financial_by_type = {
        row["claim_type_code"]: {
            "total_submitted_amount": row["total_submitted_amount"],
            "total_allowed_amount": row["total_allowed_amount"],
            "total_provider_paid_amount": row["total_provider_paid_amount"],
            "total_covered_paid_amount": row["total_covered_paid_amount"],
            "total_beneficiary_paid_amount": row["total_beneficiary_paid_amount"],
            "total_part_d_plan_paid": row["total_part_d_plan_paid"],
            "total_part_d_patient_paid": row["total_part_d_patient_paid"],
            "total_drug_cost": row["total_drug_cost"],
        }
        for row in claim_type_summary.collect()
    }
    service_systems = {
        row["service_code_system"]: row["service_count"]
        for row in service.groupBy("service_code_system").agg(F.sum("service_count").alias("service_count")).collect()
    }
    return {
        "resource_count": bronze.count(),
        "eob_count": silver["claim_header"].count(),
        "claim_line_count": silver["claim_line"].count(),
        "provider_count": silver["claim_provider"].count(),
        "financial_record_count": silver["claim_line_financial"].count(),
        "claim_types": {row["claim_type_code"]: row["claim_count"] for row in claim_type_summary.select("claim_type_code", "claim_count").collect()},
        "service_date_min": claim_type_summary.agg(F.min("service_date_min")).first()[0].isoformat(),
        "service_date_max": claim_type_summary.agg(F.max("service_date_max")).first()[0].isoformat(),
        "unique_service_codes": service.select("service_code").where(F.col("service_code").isNotNull()).distinct().count(),
        "service_code_systems": service_systems,
        "eobs_with_diagnosis_pct": pct("EOBs with diagnoses"),
        "eobs_with_provider_pct": pct("EOBs with provider attribution"),
        "claim_lines_with_financial_pct": pct("claim lines with any financial data"),
        "claim_lines_with_service_code_pct": pct("claim lines with service codes"),
        "unsupported_financial_code_count": silver["claim_line_financial"].where(F.col("mapping_status") == "unsupported").count(),
        "high_cost_claim_count": gold["high_cost_claims"].where(F.col("high_cost_flag")).count(),
        "claim_type_financial_metrics": financial_by_type,
    }


def write_gold_metric_artifacts(
    bronze: DataFrame,
    silver: dict[str, DataFrame],
    gold: dict[str, DataFrame],
    output_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Write requested Gold metrics JSON artifacts."""
    output_root = Path(output_root)
    metrics_dir = output_root / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    summary = build_gold_pipeline_summary(bronze, silver, gold)
    interview = build_interview_metrics(gold, silver, bronze)
    reconciliation = build_gold_reconciliation(silver, gold)
    (metrics_dir / "gold_pipeline_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "fhir_interview_metrics.json").write_text(json.dumps(interview, indent=2, sort_keys=True), encoding="utf-8")
    (metrics_dir / "gold_reconciliation.json").write_text(json.dumps(reconciliation, indent=2, sort_keys=True), encoding="utf-8")
    return summary, interview, reconciliation


def write_interview_findings(
    gold: dict[str, DataFrame],
    silver: dict[str, DataFrame],
    bronze: DataFrame,
    metrics: dict[str, Any],
    reconciliation: dict[str, Any],
    report_path: str | Path,
) -> None:
    """Write a markdown interview findings report from computed Gold outputs."""
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    claim_types = gold["claim_type_summary"].orderBy("claim_type_code").collect()
    service_systems = metrics["service_code_systems"]
    high_cost = gold["high_cost_claims"].where(F.col("high_cost_flag")).orderBy(F.col("cost_basis_amount").desc()).collect()
    provider_sources = {
        row["provider_source"]: row["count"]
        for row in silver["claim_provider"].groupBy("provider_source").count().collect()
    }
    provider_roles = {
        row["provider_role_code"] or "unlabeled": row["count"]
        for row in silver["claim_provider"].groupBy("provider_role_code").count().collect()
    }
    quality = gold["fhir_data_quality_summary"]
    unsupported = silver["claim_line_financial"].where(F.col("mapping_status") == "unsupported").count()
    total_financial = silver["claim_line_financial"].count()
    patient_count = silver["patient"].count()

    claim_type_lines = "\n".join(
        [
            (
                f"- `{row['claim_type_code']}`: {row['claim_count']} claims, {row['claim_line_count']} lines, "
                f"{row['financial_record_count']} financial records."
            )
            for row in claim_types
        ]
    )
    financial_lines = "\n".join(
        [
            (
                f"- `{row['claim_type_code']}`: submitted ${row['total_submitted_amount']:,.2f}; "
                f"allowed ${row['total_allowed_amount']:,.2f}; provider paid ${row['total_provider_paid_amount']:,.2f}; "
                f"covered paid ${row['total_covered_paid_amount']:,.2f}; beneficiary paid ${row['total_beneficiary_paid_amount']:,.2f}; "
                f"Part D plan paid ${row['total_part_d_plan_paid']:,.2f}; drug cost ${row['total_drug_cost']:,.2f}."
            )
            for row in claim_types
        ]
    )
    high_cost_lines = "\n".join(
        [
            f"- `{row['eob_id']}` ({row['claim_type_code']}): {row['cost_basis_name']} = ${row['cost_basis_amount']:,.2f}."
            for row in high_cost
        ]
    ) or "- No claims exceeded the configured high-cost percentile threshold."

    text = f"""# FHIR Interview Findings

## Dataset Profile

- Bronze resources: {bronze.count()}
- EOB count: {silver['claim_header'].count()}
- Claim lines: {silver['claim_line'].count()}
- Provider records: {silver['claim_provider'].count()}
- Financial records: {silver['claim_line_financial'].count()}
- Date coverage: {metrics.get('service_date_min', 'see Gold outputs')} to {metrics.get('service_date_max', 'see Gold outputs')}

## Claim Mix

{claim_type_lines}

## Financial Findings

{financial_lines}

These amounts are intentionally not collapsed into one universal paid amount. Provider-paid, covered-paid, and Part D concepts remain separate.

## Service Findings

- Unique service/product codes: {metrics['unique_service_codes']}
- Service code systems: {service_systems}
- HCPCS/CPT and NDC product vocabularies are preserved separately.

## Provider Findings

- Provider records: {silver['claim_provider'].count()}
- Provider source distribution: {provider_sources}
- Provider role distribution: {provider_roles}
- Provider reimbursement dollars are allocated only when a claim has one provider attribution. Multi-provider claims retain activity counts without multiplying reimbursement amounts.

## High-Cost Findings

- High-cost claims using within-claim-type percentiles: {len(high_cost)}
{high_cost_lines}

## FHIR Interoperability Findings

- EOBs with provider attribution: {metrics['eobs_with_provider_pct']:.1%}
- EOBs with diagnosis: {metrics['eobs_with_diagnosis_pct']:.1%}
- Claim lines with service codes: {metrics['claim_lines_with_service_code_pct']:.1%}
- Claim lines with financial data: {metrics['claim_lines_with_financial_pct']:.1%}
- Unsupported adjudication code records: {unsupported} of {total_financial}

## Engineering Findings

- EOB shapes are heterogeneous across PDE, Carrier, and Outpatient examples.
- Financial adjudication arrays were normalized into a typed component table before business aggregation.
- Raw FHIR JSON remains preserved in Bronze for auditability and remapping.
- Unknown adjudication codes are retained rather than discarded.

## Reconciliation

- Claim counts reconcile: {reconciliation['claim_counts_reconcile']}
- Line counts reconcile: {reconciliation['line_counts_reconcile']}
- Financial records reconcile: {reconciliation['financial_records_reconcile']}
- Provider attribution groups reconcile: {reconciliation['provider_groups_reconcile']}

## Limitations

- Patient resource count is {patient_count}; patient concentration findings are not meaningful.
- The fixture set contains 12 EOBs and is not population-scale.
- The downloaded CMS sample is mainly PDE; Carrier and Outpatient resources are documentation-based synthetic fixtures.
- Dates are sparse and synthetic, so monthly output should not be interpreted as a real utilization trend.
- Unsupported claim types remain future work.
- This is an engineering demonstration, not a clinical or actuarial conclusion.
"""
    report_path.write_text(text, encoding="utf-8")
