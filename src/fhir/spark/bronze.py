"""Bronze FHIR resource ingestion with Spark."""

from __future__ import annotations

import uuid
import os
import sys
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def create_spark_session(app_name: str = "healthcare-fhir-pipeline", enable_delta: bool = False) -> SparkSession:
    """Create a local/Databricks-compatible Spark session."""
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
    )
    if enable_delta:
        builder = (
            builder.config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        )
        try:
            from delta import configure_spark_with_delta_pip

            builder = configure_spark_with_delta_pip(builder)
        except ImportError:
            pass
    return builder.getOrCreate()


def read_bronze_resources(
    spark: SparkSession,
    input_path: str | Path,
    *,
    source_system: str = "cms_blue_button_synthetic",
    ingestion_run_id: str | None = None,
) -> DataFrame:
    """Read individual FHIR JSON files and Bundles into auditable Bronze rows."""
    ingestion_run_id = ingestion_run_id or str(uuid.uuid4())
    source_path = Path(input_path)
    path = str(source_path / "*.json") if source_path.is_dir() else str(source_path)
    raw = (
        spark.read.option("multiLine", True)
        .option("mode", "PERMISSIVE")
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .json(path)
        .withColumn("source_file", F.input_file_name())
        .withColumn("source_system", F.lit(source_system))
        .withColumn("ingested_at", F.current_timestamp())
        .withColumn("ingestion_run_id", F.lit(ingestion_run_id))
    )
    if "_corrupt_record" not in raw.columns:
        raw = raw.withColumn("_corrupt_record", F.lit(None).cast("string"))

    parsed_columns = [column for column in raw.columns if column not in {"entry", "source_file", "source_system", "ingested_at", "ingestion_run_id"}]
    resource_struct = F.struct(*[F.col(column) for column in parsed_columns if column != "_corrupt_record"])

    individual = raw.where((F.col("resourceType") != F.lit("Bundle")) | F.col("resourceType").isNull()).select(
        F.col("resourceType").alias("resource_type"),
        F.col("id").cast("string").alias("resource_id"),
        F.coalesce(
            F.get_json_object(F.to_json(resource_struct), "$.patient.reference"),
            F.get_json_object(F.to_json(resource_struct), "$.beneficiary.reference"),
        ).alias("patient_reference"),
        F.lit(None).cast("string").alias("bundle_id"),
        "source_file",
        "source_system",
        F.when(F.col("_corrupt_record").isNotNull(), F.col("_corrupt_record")).otherwise(F.to_json(resource_struct)).alias("raw_json"),
        "ingested_at",
        "ingestion_run_id",
        (
            F.col("_corrupt_record").isNull()
            & F.col("resourceType").isin("Patient", "Coverage", "ExplanationOfBenefit")
        ).alias("valid_resource"),
        F.when(F.col("_corrupt_record").isNotNull(), F.lit("malformed_json"))
        .when(F.col("resourceType").isNull(), F.lit("missing_resourceType"))
        .when(~F.col("resourceType").isin("Patient", "Coverage", "ExplanationOfBenefit", "Bundle"), F.lit("unsupported_resourceType"))
        .otherwise(F.lit(None).cast("string"))
        .alias("validation_error"),
    )

    if "entry" not in raw.columns:
        return individual

    bundle_entries = raw.where(F.col("resourceType") == F.lit("Bundle")).select(
        F.col("id").cast("string").alias("bundle_id"),
        "source_file",
        "source_system",
        "ingested_at",
        "ingestion_run_id",
        F.posexplode_outer("entry").alias("entry_position", "entry"),
    )

    entry_json = F.to_json(F.col("entry.resource"))
    bundle_resources = bundle_entries.select(
        F.get_json_object(entry_json, "$.resourceType").alias("resource_type"),
        F.get_json_object(entry_json, "$.id").alias("resource_id"),
        F.coalesce(
            F.get_json_object(entry_json, "$.patient.reference"),
            F.get_json_object(entry_json, "$.beneficiary.reference"),
        ).alias("patient_reference"),
        "bundle_id",
        "source_file",
        "source_system",
        entry_json.alias("raw_json"),
        "ingested_at",
        "ingestion_run_id",
        (
            F.col("entry.resource").isNotNull()
            & F.get_json_object(entry_json, "$.resourceType").isin("Patient", "Coverage", "ExplanationOfBenefit")
        ).alias("valid_resource"),
        F.when(F.col("entry").isNull(), F.lit("empty_bundle_entry"))
        .when(F.col("entry.resource").isNull(), F.lit("missing_bundle_entry_resource"))
        .when(F.get_json_object(entry_json, "$.resourceType").isNull(), F.lit("missing_resourceType"))
        .when(
            ~F.get_json_object(entry_json, "$.resourceType").isin("Patient", "Coverage", "ExplanationOfBenefit"),
            F.lit("unsupported_resourceType"),
        )
        .otherwise(F.lit(None).cast("string"))
        .alias("validation_error"),
    )

    return individual.unionByName(bundle_resources)


def build_ingestion_audit(bronze: DataFrame) -> DataFrame:
    """Build Bronze ingestion audit metrics."""
    duplicate_count = (
        bronze.where(F.col("valid_resource"))
        .groupBy("resource_type", "resource_id")
        .agg(F.count("*").alias("count"))
        .where((F.col("resource_id").isNotNull()) & (F.col("count") > 1))
        .count()
    )
    metrics = bronze.agg(
        F.first("ingestion_run_id", ignorenulls=True).alias("ingestion_run_id"),
        F.countDistinct("source_file").alias("source_file_count"),
        F.count("*").alias("resource_count"),
        F.sum(F.col("valid_resource").cast("int")).alias("valid_resource_count"),
        F.sum((~F.col("valid_resource")).cast("int")).alias("invalid_resource_count"),
        F.sum(F.col("resource_id").isNull().cast("int")).alias("missing_id_count"),
        F.sum(F.col("resource_type").isNull().cast("int")).alias("missing_resource_type_count"),
        F.sum((F.col("resource_type") == "Patient").cast("int")).alias("patient_count"),
        F.sum((F.col("resource_type") == "Coverage").cast("int")).alias("coverage_count"),
        F.sum((F.col("resource_type") == "ExplanationOfBenefit").cast("int")).alias("eob_count"),
        F.min("ingested_at").alias("started_at"),
        F.max("ingested_at").alias("completed_at"),
    )
    return metrics.withColumn("duplicate_resource_count", F.lit(duplicate_count).cast("long"))


def write_dataframe(df: DataFrame, path: str | Path, *, output_format: str = "parquet") -> None:
    """Write a DataFrame as Parquet locally or Delta in Databricks/Delta-enabled Spark."""
    df.write.mode("overwrite").format(output_format).save(str(path))
