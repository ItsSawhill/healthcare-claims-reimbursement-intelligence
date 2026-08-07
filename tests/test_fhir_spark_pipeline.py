import json
from pathlib import Path
import sys

import pytest
from pyspark.sql import functions as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.spark.bronze import build_ingestion_audit, create_spark_session, read_bronze_resources  # noqa: E402
from fhir.spark.quality import build_data_quality_results  # noqa: E402
from fhir.spark.silver import build_pipeline_summary, build_silver_tables  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button"


@pytest.fixture(scope="module")
def spark():
    session = create_spark_session("fhir-spark-tests")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def pipeline(spark):
    bronze = read_bronze_resources(spark, FIXTURE_DIR, ingestion_run_id="test-run")
    audit = build_ingestion_audit(bronze)
    silver = build_silver_tables(bronze)
    quality = build_data_quality_results(bronze, silver)
    summary = build_pipeline_summary(bronze, silver)
    return {"bronze": bronze, "audit": audit, "silver": silver, "quality": quality, "summary": summary}


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _quality_lookup(quality):
    return {row["check_name"]: row.asDict() for row in quality.collect()}


def test_bronze_ingests_patient_coverage_and_eob_resources(pipeline):
    counts = {row["resource_type"]: row["count"] for row in pipeline["bronze"].groupBy("resource_type").count().collect()}
    audit = pipeline["audit"].first().asDict()

    assert counts == {"Patient": 1, "Coverage": 4, "ExplanationOfBenefit": 12}
    assert audit["source_file_count"] == 4
    assert audit["valid_resource_count"] == 17
    assert audit["invalid_resource_count"] == 0


def test_silver_patient_and_coverage_tables(pipeline):
    patient = pipeline["silver"]["patient"].first().asDict()
    coverage_count = pipeline["silver"]["coverage"].count()

    assert patient["patient_id"] == "-20140000010000"
    assert patient["gender"] == "male"
    assert patient["state"] == "05"
    assert coverage_count == 4
    assert pipeline["silver"]["coverage"].where(F.col("coverage_end").isNull()).count() == 4


def test_silver_claim_headers_cover_pde_carrier_and_outpatient(pipeline):
    claim_types = {
        row["claim_type_code"]: row["count"]
        for row in pipeline["silver"]["claim_header"].groupBy("claim_type_code").count().collect()
    }

    assert claim_types == {"PDE": 10, "CARRIER": 1, "OUTPATIENT": 1}
    assert pipeline["silver"]["claim_header"].where(F.col("line_item_count") > 1).count() >= 1


def test_claim_lines_extract_multiple_lines_and_missing_financial_fields(pipeline):
    claim_line = pipeline["silver"]["claim_line"]

    assert claim_line.count() == 14
    assert claim_line.where(F.col("eob_id") == "carrier--local-synthetic-0001").count() == 2
    assert claim_line.where(
        (F.col("eob_id") == "outpatient--local-synthetic-0001")
        & (F.col("line_number") == 2)
        & F.col("submitted_amount").isNull()
    ).count() == 1


def test_financial_values_are_extracted_by_adjudication_code(pipeline):
    carrier_lines = pipeline["silver"]["claim_line"].where(F.col("eob_id") == "carrier--local-synthetic-0001")
    line_one = carrier_lines.where(F.col("line_number") == 1).first().asDict()
    line_two = carrier_lines.where(F.col("line_number") == 2).first().asDict()

    assert line_one["submitted_amount"] == 175.0
    assert line_one["allowed_amount"] == 95.0
    assert line_one["provider_paid_amount"] == 76.0
    assert line_one["beneficiary_paid_amount"] == 19.0
    assert line_two["submitted_amount"] == 80.0
    assert line_two["provider_paid_amount"] == 36.0


def test_financial_child_table_preserves_unknown_and_pde_specific_codes(pipeline):
    financial = pipeline["silver"]["claim_line_financial"]

    assert financial.count() == 103
    assert financial.where(F.col("adjudication_code") == "LOCAL_UNKNOWN_FINANCIAL_CODE").count() == 1
    assert financial.where(F.col("mapping_status") == "unsupported").count() == 1
    assert financial.where(F.col("analytical_category") == "part_d_total_drug_cost").count() == 10


def test_service_codes_diagnoses_and_multiple_service_codings(pipeline):
    claim_line = pipeline["silver"]["claim_line"]
    diagnosis = pipeline["silver"]["claim_diagnosis"]

    assert claim_line.where(F.col("service_code").isin("99213", "93000", "71046", "80053")).count() == 4
    assert claim_line.where(F.col("service_code_system").contains("hcpcs")).count() >= 4
    assert {row["diagnosis_code"] for row in diagnosis.select("diagnosis_code").collect()} == {"I10", "E11.9", "R07.9"}


def test_provider_attribution_prefers_careteam_and_falls_back_to_eob_provider(pipeline):
    providers = pipeline["silver"]["claim_provider"]

    assert providers.where(F.col("eob_id") == "carrier--local-synthetic-0001").count() == 2
    assert providers.where(F.col("provider_identifier") == "1999999991").count() == 1
    assert providers.where(F.col("provider_identifier") == "1888888882").count() == 1
    assert providers.where(
        (F.col("eob_id") == "outpatient--local-synthetic-0001")
        & (F.col("provider_source") == "ExplanationOfBenefit.provider.reference")
    ).count() == 1


def test_quality_and_reconciliation_metrics(pipeline):
    quality = _quality_lookup(pipeline["quality"])
    summary = pipeline["summary"]

    assert quality["unknown_adjudication_codes"]["failure_count"] == 1
    assert quality["claim_lines_without_any_financial_data"]["failure_count"] == 1
    assert quality["missing_provider_attribution"]["failure_count"] == 0
    assert summary["bronze_eob_count_equals_claim_header_count"] is True
    assert summary["claim_header_line_count_sum"] == summary["claim_line_row_count"] == 14


def test_malformed_bronze_resource_is_auditable(spark, tmp_path):
    _write_json(tmp_path / "patient.json", {"resourceType": "Patient", "id": "patient-1"})
    (tmp_path / "malformed.json").write_text('{"resourceType": "Patient",', encoding="utf-8")

    bronze = read_bronze_resources(spark, tmp_path, ingestion_run_id="bad-json-test")

    assert bronze.where(~F.col("valid_resource")).count() == 1
    assert bronze.where(F.col("validation_error") == "malformed_json").count() == 1


def test_duplicate_ids_are_flagged(spark, tmp_path):
    _write_json(tmp_path / "patient_a.json", {"resourceType": "Patient", "id": "dup-patient"})
    _write_json(tmp_path / "patient_b.json", {"resourceType": "Patient", "id": "dup-patient"})

    bronze = read_bronze_resources(spark, tmp_path, ingestion_run_id="duplicate-test")
    silver = build_silver_tables(bronze)
    quality = _quality_lookup(build_data_quality_results(bronze, silver))

    assert quality["duplicate_patient_ids"]["failure_count"] == 1


def test_negative_financial_values_are_flagged(spark, tmp_path):
    _write_json(
        tmp_path / "negative_eob.json",
        {
            "resourceType": "ExplanationOfBenefit",
            "id": "eob-negative",
            "status": "active",
            "type": {"coding": [{"system": "https://bluebutton.cms.gov/resources/codesystem/eob-type", "code": "CARRIER"}]},
            "patient": {"reference": "Patient/patient-1"},
            "billablePeriod": {"start": "2024-01-01", "end": "2024-01-01"},
            "provider": {"identifier": {"value": "1234567890"}},
            "item": [
                {
                    "sequence": 1,
                    "service": {"coding": [{"system": "https://bluebutton.cms.gov/resources/codesystem/hcpcs", "code": "99213"}]},
                    "servicedDate": "2024-01-01",
                    "adjudication": [
                        {
                            "category": {
                                "coding": [
                                    {
                                        "system": "https://bluebutton.cms.gov/fhir/CodeSystem/Adjudication",
                                        "code": "CLM_LINE_PRVDR_PMT_AMT",
                                    }
                                ]
                            },
                            "amount": {"value": -5.0, "currency": "USD"},
                        }
                    ],
                }
            ],
        },
    )

    bronze = read_bronze_resources(spark, tmp_path, ingestion_run_id="negative-test")
    silver = build_silver_tables(bronze)
    quality = _quality_lookup(build_data_quality_results(bronze, silver))

    assert quality["negative_financial_values"]["failure_count"] == 1
