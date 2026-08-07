from pathlib import Path
import sys

import pytest
from pyspark.sql import functions as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.spark.bronze import create_spark_session, read_bronze_resources  # noqa: E402
from fhir.spark.gold import build_gold_tables  # noqa: E402
from fhir.spark.quality import build_data_quality_results  # noqa: E402
from fhir.spark.reconciliation import build_gold_reconciliation  # noqa: E402
from fhir.spark.silver import build_silver_tables  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button"


@pytest.fixture(scope="module")
def spark():
    session = create_spark_session("fhir-gold-tests")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def pipeline(spark):
    bronze = read_bronze_resources(spark, FIXTURE_DIR, ingestion_run_id="gold-test")
    silver = build_silver_tables(bronze)
    quality = build_data_quality_results(bronze, silver)
    gold = build_gold_tables(bronze, silver, quality)
    reconciliation = build_gold_reconciliation(silver, gold)
    return {"bronze": bronze, "silver": silver, "quality": quality, "gold": gold, "reconciliation": reconciliation}


def _rows_by(df, key):
    return {row[key]: row.asDict() for row in df.collect()}


def test_claim_type_summary_totals_preserve_payment_semantics(pipeline):
    summary = _rows_by(pipeline["gold"]["claim_type_summary"], "claim_type_code")

    assert summary["CARRIER"]["claim_count"] == 1
    assert summary["CARRIER"]["total_submitted_amount"] == 255.0
    assert summary["CARRIER"]["total_provider_paid_amount"] == 112.0
    assert summary["OUTPATIENT"]["total_submitted_amount"] == 220.0
    assert summary["OUTPATIENT"]["total_covered_paid_amount"] == 118.0
    assert summary["PDE"]["total_drug_cost"] == 210.0
    assert summary["PDE"]["total_provider_paid_amount"] == 0.0


def test_financial_component_aggregation_reconciles_to_silver_financial(pipeline):
    component = pipeline["gold"]["financial_component_summary"]
    silver_financial = pipeline["silver"]["claim_line_financial"]

    assert component.agg(F.sum("record_count")).first()[0] == silver_financial.count()
    submitted = component.where(F.col("adjudication_code") == "CLM_LINE_SBMT_CHRG_AMT").agg(
        F.sum("record_count").alias("record_count"),
        F.sum("total_amount").alias("total_amount"),
    ).first().asDict()
    assert submitted["record_count"] == 3
    assert submitted["total_amount"] == 475.0


def test_hcpcs_cpt_and_ndc_service_systems_remain_distinct(pipeline):
    service = pipeline["gold"]["service_cost_summary"]
    systems = {row["service_code_system"] for row in service.select("service_code_system").distinct().collect()}

    assert "http://hl7.org/fhir/sid/ndc" in systems
    assert "https://bluebutton.cms.gov/resources/codesystem/hcpcs" in systems
    assert service.where((F.col("claim_type_code") == "PDE") & (F.col("service_code_system") == "http://hl7.org/fhir/sid/ndc")).count() == 9
    assert service.where(F.col("service_code").isin("99213", "93000", "71046", "80053")).count() == 4


def test_provider_reimbursement_does_not_double_count_multi_provider_claim_money(pipeline):
    provider = pipeline["gold"]["provider_reimbursement"]

    carrier_provider_paid = provider.where(F.col("claim_type_code") == "CARRIER").agg(F.sum("total_provider_paid_amount")).first()[0]
    outpatient_covered = provider.where(F.col("claim_type_code") == "OUTPATIENT").agg(F.sum("total_covered_paid_amount")).first()[0]
    assert carrier_provider_paid == 0.0
    assert outpatient_covered == 118.0
    assert provider.where(F.col("claim_type_code") == "CARRIER").count() == 2


def test_patient_utilization_handles_one_patient_limitation(pipeline):
    patient = pipeline["gold"]["patient_utilization"].first().asDict()

    assert pipeline["gold"]["patient_utilization"].count() == 1
    assert patient["claim_count"] == 12
    assert patient["claim_line_count"] == 14
    assert patient["claim_type_count"] == 3


def test_monthly_reimbursement_uses_sparse_months_without_trend_metrics(pipeline):
    monthly = pipeline["gold"]["monthly_reimbursement"]

    assert monthly.count() == 8
    assert "month_over_month_change" not in monthly.columns
    assert monthly.where(F.col("claim_type_code") == "PDE").count() == 6


def test_high_cost_claims_use_claim_type_specific_cost_basis(pipeline):
    high_cost = pipeline["gold"]["high_cost_claims"]
    rows = _rows_by(high_cost, "claim_type_code")

    assert rows["CARRIER"]["cost_basis_name"] == "provider_paid_amount"
    assert rows["OUTPATIENT"]["cost_basis_name"] == "covered_paid_amount"
    assert high_cost.where((F.col("claim_type_code") == "PDE") & (F.col("cost_basis_name") == "part_d_total_drug_cost")).count() == 10
    assert high_cost.where(F.col("high_cost_flag")).count() == 3


def test_fhir_data_quality_gold_reports_completeness_and_unknown_codes(pipeline):
    quality = pipeline["gold"]["fhir_data_quality_summary"]

    pde_diag = quality.where((F.col("claim_type_code") == "PDE") & (F.col("metric_name") == "EOBs with diagnoses")).first().asDict()
    unsupported = quality.where(F.col("metric_name") == "unsupported financial code rate").agg(F.sum("numerator")).first()[0]
    line_financial = quality.where(F.col("metric_name") == "claim lines with any financial data").agg(
        F.sum("numerator").alias("num"), F.sum("denominator").alias("den")
    ).first()

    assert pde_diag["percentage"] == 0.0
    assert unsupported == 1
    assert line_financial["num"] == 13
    assert line_financial["den"] == 14


def test_gold_silver_reconciliation(pipeline):
    reconciliation = pipeline["reconciliation"]

    assert reconciliation["claim_counts_reconcile"] is True
    assert reconciliation["line_counts_reconcile"] is True
    assert reconciliation["financial_records_reconcile"] is True
    assert reconciliation["service_counts_reconcile"] is True
    assert reconciliation["provider_groups_reconcile"] is True
