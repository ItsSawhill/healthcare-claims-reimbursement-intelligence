"""Silver FHIR normalization transformations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .schemas import (
    ADDRESS_SCHEMA,
    CARE_TEAM_SCHEMA,
    CMS_ADJUDICATION_SYSTEMS,
    CODING_SCHEMA,
    COVERAGE_PAYOR_SCHEMA,
    COVERAGE_TYPE_SCHEMA,
    DIAGNOSIS_SCHEMA,
    FINANCIAL_CODE_MAPPING,
    INSURANCE_SCHEMA,
    ITEM_SCHEMA,
    PERIOD_SCHEMA,
    SUPPORTED_OBSERVED_CLAIM_TYPES,
)


def _valid(bronze: DataFrame, resource_type: str) -> DataFrame:
    return bronze.where((F.col("valid_resource")) & (F.col("resource_type") == resource_type))


def _ref_id(column: F.Column) -> F.Column:
    return F.regexp_extract(column, r"([^/]+)$", 1)


def _claim_type_expr(type_col: F.Column) -> F.Column:
    return F.coalesce(
        F.expr(
            "element_at(transform(filter(type_coding, x -> x.system = 'https://bluebutton.cms.gov/resources/codesystem/eob-type' "
            "or x.system = 'https://bluebutton.cms.gov/resources/codesystem/eob-type'), x -> x.code), 1)"
        ),
        F.expr(
            "element_at(transform(filter(type_coding, x -> array_contains(array('PDE','CARRIER','OUTPATIENT'), x.code)), x -> x.code), 1)"
        ),
        F.expr("element_at(transform(type_coding, x -> x.code), 1)"),
    )


def transform_patient(bronze: DataFrame) -> DataFrame:
    """Normalize Patient resources."""
    patients = _valid(bronze, "Patient").select(
        F.col("resource_id").alias("source_resource_id"),
        F.get_json_object("raw_json", "$.id").alias("patient_id"),
        F.get_json_object("raw_json", "$.gender").alias("gender"),
        F.to_date(F.get_json_object("raw_json", "$.birthDate")).alias("birth_date"),
        F.when(
            F.get_json_object("raw_json", "$.deceasedBoolean").cast("boolean")
            | F.get_json_object("raw_json", "$.deceasedDateTime").isNotNull(),
            F.lit(True),
        )
        .otherwise(F.lit(False))
        .alias("deceased_flag"),
        F.from_json(F.get_json_object("raw_json", "$.address"), ADDRESS_SCHEMA).alias("address"),
    )
    selected_address = patients.withColumn(
        "selected_address",
        F.coalesce(
            F.expr("element_at(filter(address, x -> x.use = 'home'), 1)"),
            F.element_at(F.col("address"), 1),
        ),
    )
    return selected_address.select(
        "patient_id",
        "gender",
        "birth_date",
        "deceased_flag",
        F.col("selected_address.state").alias("state"),
        F.col("selected_address.postalCode").alias("postal_code"),
        "source_resource_id",
    )


def transform_coverage(bronze: DataFrame) -> DataFrame:
    """Normalize Coverage resources."""
    coverage = _valid(bronze, "Coverage").select(
        F.col("resource_id").alias("source_resource_id"),
        "source_dataset",
        "provenance_classification",
        F.get_json_object("raw_json", "$.id").alias("coverage_id"),
        _ref_id(F.get_json_object("raw_json", "$.beneficiary.reference")).alias("patient_id"),
        F.get_json_object("raw_json", "$.status").alias("coverage_status"),
        F.from_json(F.get_json_object("raw_json", "$.type"), COVERAGE_TYPE_SCHEMA).alias("coverage_type"),
        F.get_json_object("raw_json", "$.subscriber.reference").alias("subscriber_reference"),
        F.from_json(F.get_json_object("raw_json", "$.payor"), COVERAGE_PAYOR_SCHEMA).alias("payor"),
        F.from_json(F.get_json_object("raw_json", "$.period"), PERIOD_SCHEMA).alias("period"),
    )
    return coverage.select(
        "coverage_id",
        "patient_id",
        "coverage_status",
        F.expr("element_at(transform(coverage_type.coding, x -> x.code), 1)").alias("coverage_type_code"),
        F.expr("element_at(transform(coverage_type.coding, x -> x.display), 1)").alias("coverage_type_display"),
        "subscriber_reference",
        F.expr("element_at(transform(payor, x -> x.reference), 1)").alias("payor_reference"),
        F.to_date(F.col("period.start")).alias("coverage_start"),
        F.to_date(F.col("period.end")).alias("coverage_end"),
        "source_resource_id",
        "source_dataset",
        "provenance_classification",
    )


def _eob_base(bronze: DataFrame) -> DataFrame:
    eobs = _valid(bronze, "ExplanationOfBenefit").select(
        F.col("resource_id").alias("source_resource_id"),
        F.get_json_object("raw_json", "$.id").alias("eob_id"),
        F.get_json_object("raw_json", "$.status").alias("claim_status"),
        _ref_id(F.get_json_object("raw_json", "$.patient.reference")).alias("patient_id"),
        F.get_json_object("raw_json", "$.provider.reference").alias("provider_reference"),
        F.get_json_object("raw_json", "$.provider.identifier.value").alias("provider_identifier"),
        F.from_json(F.get_json_object("raw_json", "$.type.coding"), f"array<{CODING_SCHEMA.simpleString()}>").alias("type_coding"),
        F.from_json(F.get_json_object("raw_json", "$.billablePeriod"), PERIOD_SCHEMA).alias("billable_period"),
        F.from_json(F.get_json_object("raw_json", "$.insurance"), INSURANCE_SCHEMA).alias("insurance"),
        F.from_json(F.get_json_object("raw_json", "$.careTeam"), CARE_TEAM_SCHEMA).alias("careTeam"),
        F.from_json(F.get_json_object("raw_json", "$.diagnosis"), DIAGNOSIS_SCHEMA).alias("diagnosis"),
        F.from_json(F.get_json_object("raw_json", "$.item"), ITEM_SCHEMA).alias("item"),
        F.get_json_object("raw_json", "$.payment.amount.value").cast("double").alias("claim_payment_amount"),
    )
    return eobs.withColumn("claim_type_code", _claim_type_expr(F.col("type_coding"))).withColumn(
        "claim_type_display",
        F.coalesce(
            F.expr("element_at(transform(filter(type_coding, x -> x.code = claim_type_code), x -> x.display), 1)"),
            F.expr("element_at(transform(type_coding, x -> x.display), 1)"),
        ),
    )


def transform_claim_header(bronze: DataFrame) -> DataFrame:
    """Normalize EOB claim headers without creating a universal paid amount."""
    eobs = _eob_base(bronze)
    return eobs.select(
        "eob_id",
        "patient_id",
        "claim_status",
        "claim_type_code",
        "claim_type_display",
        F.to_date(F.col("billable_period.start")).alias("service_start"),
        F.to_date(F.col("billable_period.end")).alias("service_end"),
        (
            F.datediff(F.to_date(F.col("billable_period.end")), F.to_date(F.col("billable_period.start"))) + F.lit(1)
        ).alias("service_duration_days"),
        F.coalesce("provider_reference", "provider_identifier").alias("provider_reference"),
        F.expr("element_at(transform(insurance, x -> x.coverage.reference), 1)").alias("coverage_reference"),
        F.coalesce(F.size("diagnosis"), F.lit(0)).alias("diagnosis_count"),
        F.coalesce(F.size("item"), F.lit(0)).alias("line_item_count"),
        "source_resource_id",
        "claim_payment_amount",
    )


def _claim_items(bronze: DataFrame) -> DataFrame:
    return _eob_base(bronze).select(
        "eob_id",
        "patient_id",
        "claim_type_code",
        "source_resource_id",
        F.posexplode_outer("item").alias("item_index", "line"),
    )


def _preferred_coding_expr(coding_col: str) -> F.Column:
    return F.coalesce(
        F.expr(f"element_at(filter({coding_col}, x -> x.system like '%hcpcs%'), 1)"),
        F.expr(f"element_at(filter({coding_col}, x -> x.system like '%cpt%'), 1)"),
        F.expr(f"element_at({coding_col}, 1)"),
    )


def _preferred_adjudication_code_expr() -> F.Column:
    systems = ",".join([f"'{system}'" for system in CMS_ADJUDICATION_SYSTEMS])
    known_codes = ",".join([f"'{code}'" for code in FINANCIAL_CODE_MAPPING])
    return F.coalesce(
        F.expr(f"element_at(transform(filter(category_coding, x -> array_contains(array({systems}), x.system)), x -> x.code), 1)"),
        F.expr(f"element_at(transform(filter(category_coding, x -> array_contains(array({known_codes}), x.code)), x -> x.code), 1)"),
        F.expr("element_at(transform(category_coding, x -> x.code), 1)"),
    )


def transform_claim_line_financial(bronze: DataFrame) -> DataFrame:
    """Normalize every observed item adjudication coding and amount."""
    mapping_rows = [(code, status, category) for code, (status, category) in FINANCIAL_CODE_MAPPING.items()]
    mapping = bronze.sparkSession.createDataFrame(mapping_rows, ["adjudication_code", "mapping_status", "analytical_category"])
    items = _claim_items(bronze).where(F.col("line").isNotNull())
    adjudications = items.select(
        "eob_id",
        F.col("line.sequence").alias("line_number"),
        "claim_type_code",
        "source_resource_id",
        F.explode_outer("line.adjudication").alias("adjudication"),
    ).where(F.col("adjudication").isNotNull())
    preferred = adjudications.select(
        "eob_id",
        "line_number",
        "claim_type_code",
        "source_resource_id",
        F.col("adjudication.amount.value").alias("amount"),
        F.col("adjudication.amount.currency").alias("currency"),
        F.from_json(F.to_json(F.col("adjudication.category.coding")), f"array<{CODING_SCHEMA.simpleString()}>").alias("category_coding"),
    ).withColumn("adjudication_code", _preferred_adjudication_code_expr())
    financial = preferred.withColumn(
        "preferred_coding",
        F.expr("element_at(filter(category_coding, x -> x.code = adjudication_code), 1)"),
    ).select(
        "eob_id",
        "line_number",
        "claim_type_code",
        "adjudication_code",
        F.col("preferred_coding.display").alias("adjudication_display"),
        F.col("preferred_coding.system").alias("code_system"),
        "amount",
        "currency",
        "source_resource_id",
    )
    return (
        financial.join(mapping, "adjudication_code", "left")
        .withColumn("mapping_status", F.coalesce(F.col("mapping_status"), F.lit("unsupported")))
        .withColumn("analytical_category", F.coalesce(F.col("analytical_category"), F.lit("unknown")))
        .select(
            "eob_id",
            "line_number",
            "claim_type_code",
            "adjudication_code",
            "adjudication_display",
            "code_system",
            "amount",
            "currency",
            "mapping_status",
            "analytical_category",
            "source_resource_id",
        )
    )


def _preferred_financial(bronze: DataFrame) -> DataFrame:
    items = _claim_items(bronze).where(F.col("line").isNotNull())
    adjudications = items.select(
        "eob_id",
        F.col("line.sequence").alias("line_number"),
        F.explode_outer("line.adjudication").alias("adjudication"),
    ).where(F.col("adjudication").isNotNull())
    preferred = adjudications.select(
        "eob_id",
        "line_number",
        F.col("adjudication.amount.value").alias("amount"),
        F.from_json(F.to_json(F.col("adjudication.category.coding")), f"array<{CODING_SCHEMA.simpleString()}>").alias("category_coding"),
    ).withColumn("adjudication_code", _preferred_adjudication_code_expr())

    mapping_rows = [(code, category) for code, (_, category) in FINANCIAL_CODE_MAPPING.items()]
    mapping = bronze.sparkSession.createDataFrame(mapping_rows, ["adjudication_code", "analytical_category"])
    return preferred.join(mapping, "adjudication_code", "left")


def transform_claim_line(bronze: DataFrame) -> DataFrame:
    """Normalize claim lines and aggregate confirmed line-level financial concepts by code."""
    items = _claim_items(bronze).where(F.col("line").isNotNull())
    service = items.withColumn(
        "service_coding",
        _preferred_coding_expr("coalesce(line.service.coding, line.productOrService.coding)"),
    ).select(
        "eob_id",
        F.col("line.sequence").alias("line_number"),
        "patient_id",
        "claim_type_code",
        F.coalesce(F.to_date("line.servicedDate"), F.to_date("line.servicedPeriod.start")).alias("service_date"),
        F.col("service_coding.code").alias("service_code"),
        F.col("service_coding.display").alias("service_display"),
        F.col("service_coding.system").alias("service_code_system"),
        F.col("line.quantity.value").alias("quantity"),
        "source_resource_id",
    )
    financial = _preferred_financial(bronze).groupBy("eob_id", "line_number").agg(
        F.sum(F.when(F.col("analytical_category") == "submitted_amount", F.col("amount"))).alias("submitted_amount"),
        F.sum(F.when(F.col("analytical_category") == "allowed_amount", F.col("amount"))).alias("allowed_amount"),
        F.sum(F.when(F.col("analytical_category") == "provider_paid_amount", F.col("amount"))).alias("provider_paid_amount"),
        F.sum(F.when(F.col("analytical_category") == "covered_paid_amount", F.col("amount"))).alias("covered_paid_amount"),
        F.sum(F.when(F.col("analytical_category") == "beneficiary_paid_amount", F.col("amount"))).alias("beneficiary_paid_amount"),
        F.sum(F.when(F.col("analytical_category") == "deductible_amount", F.col("amount"))).alias("deductible_amount"),
        F.sum(F.when(F.col("analytical_category") == "coinsurance_amount", F.col("amount"))).alias("coinsurance_amount"),
        F.sum(F.when(F.col("analytical_category") == "noncovered_amount", F.col("amount"))).alias("noncovered_amount"),
    )
    return service.join(financial, ["eob_id", "line_number"], "left").select(
        "eob_id",
        "line_number",
        "patient_id",
        "claim_type_code",
        "service_date",
        "service_code",
        "service_display",
        "service_code_system",
        "quantity",
        "submitted_amount",
        "allowed_amount",
        "provider_paid_amount",
        "covered_paid_amount",
        "beneficiary_paid_amount",
        "deductible_amount",
        "coinsurance_amount",
        "noncovered_amount",
        "source_resource_id",
    )


def transform_claim_diagnosis(bronze: DataFrame) -> DataFrame:
    """Normalize claim diagnosis rows."""
    eobs = _eob_base(bronze).select("eob_id", "patient_id", "source_resource_id", F.explode_outer("diagnosis").alias("diagnosis"))
    typed = eobs.where(F.col("diagnosis").isNotNull()).withColumn(
        "diagnosis_coding",
        F.expr("element_at(diagnosis.diagnosisCodeableConcept.coding, 1)"),
    )
    return typed.select(
        "eob_id",
        "patient_id",
        F.col("diagnosis.sequence").alias("diagnosis_sequence"),
        F.col("diagnosis_coding.code").alias("diagnosis_code"),
        F.col("diagnosis_coding.display").alias("diagnosis_display"),
        F.col("diagnosis_coding.system").alias("diagnosis_code_system"),
        F.expr("concat_ws('|', flatten(transform(diagnosis.type, x -> transform(x.coding, y -> y.code))))").alias("diagnosis_type"),
        "source_resource_id",
    )


def transform_claim_provider(bronze: DataFrame) -> DataFrame:
    """Normalize claim provider attribution with careTeam preferred and provider fallback."""
    eobs = _eob_base(bronze).select(
        "eob_id",
        "patient_id",
        "source_resource_id",
        "provider_reference",
        "provider_identifier",
        "careTeam",
    )
    care_team = eobs.select(
        "eob_id",
        "patient_id",
        "source_resource_id",
        F.explode_outer("careTeam").alias("care_team"),
    ).where(F.col("care_team").isNotNull())
    care_team_rows = care_team.select(
        "eob_id",
        "patient_id",
        F.col("care_team.provider.identifier.value").alias("provider_identifier"),
        F.col("care_team.provider.reference").alias("provider_reference"),
        F.expr("element_at(transform(care_team.role.coding, x -> x.code), 1)").alias("provider_role_code"),
        F.expr("element_at(transform(care_team.role.coding, x -> x.display), 1)").alias("provider_role_display"),
        F.lit("careTeam.provider").alias("provider_source"),
        "source_resource_id",
    )
    fallback = eobs.join(care_team_rows.select("eob_id").distinct(), "eob_id", "left_anti").where(
        F.col("provider_reference").isNotNull() | F.col("provider_identifier").isNotNull()
    )
    fallback_rows = fallback.select(
        "eob_id",
        "patient_id",
        F.col("provider_identifier"),
        F.col("provider_reference"),
        F.lit(None).cast("string").alias("provider_role_code"),
        F.lit(None).cast("string").alias("provider_role_display"),
        F.when(F.col("provider_identifier").isNotNull(), F.lit("ExplanationOfBenefit.provider.identifier"))
        .otherwise(F.lit("ExplanationOfBenefit.provider.reference"))
        .alias("provider_source"),
        "source_resource_id",
    )
    return care_team_rows.unionByName(fallback_rows)


def build_silver_tables(bronze: DataFrame) -> dict[str, DataFrame]:
    """Build all Silver FHIR tables from Bronze resources."""
    patient = transform_patient(bronze)
    coverage = transform_coverage(bronze)
    claim_header = transform_claim_header(bronze)
    claim_line_financial = transform_claim_line_financial(bronze)
    claim_line = transform_claim_line(bronze)
    claim_diagnosis = transform_claim_diagnosis(bronze)
    claim_provider = transform_claim_provider(bronze)
    return {
        "patient": patient,
        "coverage": coverage,
        "claim_header": claim_header,
        "claim_line": claim_line,
        "claim_line_financial": claim_line_financial,
        "claim_diagnosis": claim_diagnosis,
        "claim_provider": claim_provider,
    }


def write_silver_tables(tables: dict[str, DataFrame], base_path: str | Path, *, output_format: str = "parquet") -> None:
    """Write Silver tables under a base path."""
    for name, frame in tables.items():
        frame.write.mode("overwrite").format(output_format).save(str(Path(base_path) / name))


def build_pipeline_summary(bronze: DataFrame, silver: dict[str, DataFrame]) -> dict[str, Any]:
    """Compute reconciliation and summary metrics for local/Databricks runs."""
    header = silver["claim_header"]
    line = silver["claim_line"]
    financial = silver["claim_line_financial"]
    service_dates = header.agg(F.min("service_start").alias("min_date"), F.max("service_end").alias("max_date")).first()
    claim_types = {row["claim_type_code"]: row["count"] for row in header.groupBy("claim_type_code").count().collect()}
    return {
        "bronze_resource_count": bronze.count(),
        "patient_count": silver["patient"].count(),
        "coverage_count": silver["coverage"].count(),
        "eob_count": header.count(),
        "claim_line_count": line.count(),
        "diagnosis_count": silver["claim_diagnosis"].count(),
        "provider_count": silver["claim_provider"].count(),
        "financial_record_count": financial.count(),
        "unknown_adjudication_code_count": financial.where(F.col("mapping_status") == "unsupported").select("adjudication_code").distinct().count(),
        "claim_types": claim_types,
        "service_date_min": service_dates["min_date"].isoformat() if service_dates["min_date"] else None,
        "service_date_max": service_dates["max_date"].isoformat() if service_dates["max_date"] else None,
        "bronze_eob_count_equals_claim_header_count": bronze.where(F.col("resource_type") == "ExplanationOfBenefit").count() == header.count(),
        "claim_header_line_count_sum": header.agg(F.sum("line_item_count")).first()[0],
        "claim_line_row_count": line.count(),
    }


def write_summary_artifacts(summary: dict[str, Any], claim_header: DataFrame, output_root: str | Path) -> None:
    """Write JSON summary and claim-type summary CSV artifacts."""
    output_root = Path(output_root)
    metrics_dir = output_root / "metrics"
    tables_dir = output_root / "tables"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "silver_pipeline_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    claim_header.groupBy("claim_type_code").agg(
        F.count("*").alias("claim_count"),
        F.sum("line_item_count").alias("line_item_count"),
        F.sum("diagnosis_count").alias("diagnosis_count"),
    ).coalesce(1).write.mode("overwrite").option("header", True).csv(str(tables_dir / "silver_claim_type_summary.csv.tmp"))
