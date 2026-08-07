"""Data quality checks for FHIR Silver tables."""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .schemas import SUPPORTED_OBSERVED_CLAIM_TYPES


def _check_row(
    spark: SparkSession,
    *,
    check_name: str,
    table_name: str,
    record_count: int,
    failure_count: int,
    severity: str,
    details: str,
) -> DataFrame:
    return spark.createDataFrame(
        [
            {
                "check_name": check_name,
                "table_name": table_name,
                "record_count": record_count,
                "failure_count": failure_count,
                "failure_percentage": (failure_count / record_count) if record_count else 0.0,
                "severity": severity,
                "details": details,
            }
        ]
    )


def _duplicate_failures(df: DataFrame, column: str) -> int:
    return df.where(F.col(column).isNotNull()).groupBy(column).count().where(F.col("count") > 1).count()


def build_data_quality_results(bronze: DataFrame, silver: dict[str, DataFrame]) -> DataFrame:
    """Run structural, completeness, and unsupported-mapping quality checks."""
    spark = bronze.sparkSession
    patient = silver["patient"]
    coverage = silver["coverage"]
    header = silver["claim_header"]
    line = silver["claim_line"]
    diagnosis = silver["claim_diagnosis"]
    provider = silver["claim_provider"]
    financial = silver["claim_line_financial"]

    checks: list[DataFrame] = []

    checks.append(
        _check_row(
            spark,
            check_name="duplicate_patient_ids",
            table_name="patient",
            record_count=patient.count(),
            failure_count=_duplicate_failures(patient, "patient_id"),
            severity="structural_error",
            details="Patient IDs should be unique in Silver patient.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="duplicate_coverage_ids",
            table_name="coverage",
            record_count=coverage.count(),
            failure_count=_duplicate_failures(coverage, "coverage_id"),
            severity="structural_error",
            details="Coverage IDs should be unique in Silver coverage.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="duplicate_eob_ids",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=_duplicate_failures(header, "eob_id"),
            severity="structural_error",
            details="EOB IDs should be unique in Silver claim_header.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="missing_patient_references",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=header.where(F.col("patient_id").isNull() | (F.col("patient_id") == "")).count(),
            severity="structural_error",
            details="Every EOB should retain a patient reference.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="missing_claim_types",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=header.where(F.col("claim_type_code").isNull()).count(),
            severity="structural_error",
            details="EOB type.coding should provide a claim type.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="invalid_service_periods",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=header.where(F.col("service_end") < F.col("service_start")).count(),
            severity="structural_error",
            details="Service end date should not precede service start date.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="missing_service_codes",
            table_name="claim_line",
            record_count=line.count(),
            failure_count=line.where(F.col("service_code").isNull()).count(),
            severity="completeness_warning",
            details="Line service or product code is missing.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="negative_financial_values",
            table_name="claim_line_financial",
            record_count=financial.count(),
            failure_count=financial.where(F.col("amount") < 0).count(),
            severity="structural_error",
            details="Financial adjudication amounts should not be negative.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="claim_line_without_matching_eob",
            table_name="claim_line",
            record_count=line.count(),
            failure_count=line.join(header.select("eob_id"), "eob_id", "left_anti").count(),
            severity="structural_error",
            details="Every claim line should link to a claim_header row.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="diagnosis_without_matching_eob",
            table_name="claim_diagnosis",
            record_count=diagnosis.count(),
            failure_count=diagnosis.join(header.select("eob_id"), "eob_id", "left_anti").count(),
            severity="structural_error",
            details="Every diagnosis row should link to a claim_header row.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="unknown_adjudication_codes",
            table_name="claim_line_financial",
            record_count=financial.count(),
            failure_count=financial.where(F.col("mapping_status") == "unsupported").count(),
            severity="unsupported_mapping",
            details="Unsupported adjudication codes remain auditable in claim_line_financial.",
        )
    )
    financial_lines = financial.select("eob_id", "line_number").distinct()
    line_without_financial = line.join(financial_lines, ["eob_id", "line_number"], "left_anti")
    checks.append(
        _check_row(
            spark,
            check_name="claim_lines_without_any_financial_data",
            table_name="claim_line",
            record_count=line.count(),
            failure_count=line_without_financial.count(),
            severity="completeness_warning",
            details="Some FHIR line items may omit adjudication arrays.",
        )
    )
    provider_eobs = provider.select("eob_id").distinct()
    checks.append(
        _check_row(
            spark,
            check_name="missing_provider_attribution",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=header.join(provider_eobs, "eob_id", "left_anti").count(),
            severity="completeness_warning",
            details="Provider attribution uses careTeam first, then EOB provider fallback.",
        )
    )
    checks.append(
        _check_row(
            spark,
            check_name="unsupported_claim_types",
            table_name="claim_header",
            record_count=header.count(),
            failure_count=header.where(~F.col("claim_type_code").isin(SUPPORTED_OBSERVED_CLAIM_TYPES)).count(),
            severity="unsupported_mapping",
            details="Only observed PDE, CARRIER, and OUTPATIENT claim profiles are supported in Phase 2.",
        )
    )

    output = checks[0]
    for check in checks[1:]:
        output = output.unionByName(check)
    return output


def summarize_quality_results(quality: DataFrame) -> DataFrame:
    """Return a compact quality summary for CSV output."""
    return quality.select(
        "check_name",
        "table_name",
        "record_count",
        "failure_count",
        "failure_percentage",
        "severity",
        "details",
    )
