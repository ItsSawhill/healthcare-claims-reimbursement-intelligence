from pathlib import Path
import sys

from pyspark.sql import functions as F
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.population_generator import write_population_bundle  # noqa: E402
from fhir.spark.bronze import create_spark_session, deduplicate_bronze_resources, read_bronze_resources  # noqa: E402
from fhir.spark.gold import build_gold_tables  # noqa: E402
from fhir.spark.population import build_population_reconciliation  # noqa: E402
from fhir.spark.quality import build_data_quality_results  # noqa: E402
from fhir.spark.silver import build_silver_tables  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    session = create_spark_session("fhir-population-tests")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def population_pipeline(tmp_path_factory, spark):
    fixture_dir = tmp_path_factory.mktemp("phase4-population")
    write_population_bundle(fixture_dir / "population.json", beneficiary_count=6)
    bronze = deduplicate_bronze_resources(read_bronze_resources(spark, fixture_dir, ingestion_run_id="population-test"))
    silver = build_silver_tables(bronze)
    quality = build_data_quality_results(bronze, silver)
    gold = build_gold_tables(bronze, silver, quality)
    return {"bronze": bronze, "silver": silver, "quality": quality, "gold": gold}


def test_population_bronze_silver_has_multiple_patients_and_provenance(population_pipeline):
    bronze = population_pipeline["bronze"]
    silver = population_pipeline["silver"]

    assert silver["patient"].count() == 6
    assert bronze.where(F.col("provenance_classification") == "official_cms_synthetic").count() > 0
    assert bronze.where(F.col("provenance_classification") == "documentation_based_fixture").count() > 0


def test_member_months_handle_open_ended_and_overlapping_coverage(population_pipeline):
    member_months = population_pipeline["gold"]["member_months"]

    assert member_months.count() > 0
    duplicates = member_months.groupBy("patient_id", "coverage_month", "coverage_type_code").count().where(F.col("count") > 1).count()
    assert duplicates == 0


def test_pmpm_is_claim_type_specific_without_universal_paid(population_pipeline):
    pmpm = population_pipeline["gold"]["pmpm_summary"]

    assert pmpm.where(F.col("member_months") > 0).count() > 0
    assert "pmpm_paid" not in pmpm.columns
    assert {"pmpm_provider_paid", "pmpm_covered_paid", "pmpm_drug_cost"} <= set(pmpm.columns)


def test_patient_spending_concentration_and_utilization_percentiles(population_pipeline):
    concentration = population_pipeline["gold"]["patient_spending_concentration"]

    assert concentration.count() == 6
    assert concentration.where(F.col("top_10_pct_flag")).count() >= 1
    assert concentration.agg(F.max("cumulative_spend_share")).first()[0] == 1.0


def test_provider_population_summary_protects_double_counting(population_pipeline):
    providers = population_pipeline["gold"]["provider_population_summary"]

    assert providers.count() > 0
    assert "attributable_cost_basis_total" in providers.columns
    assert providers.where(F.col("claim_count") > 0).count() > 0


def test_high_cost_and_population_reconciliation(population_pipeline):
    gold = population_pipeline["gold"]
    reconciliation = build_population_reconciliation(population_pipeline["bronze"], population_pipeline["silver"], gold)

    assert gold["high_cost_claims"].where(F.col("high_cost_flag")).count() > 0
    assert reconciliation["bronze_eob_reconciles"] is True
    assert reconciliation["claim_lines_reconcile"] is True
    assert reconciliation["financial_records_reconcile"] is True
    assert reconciliation["member_month_uniqueness_reconciles"] is True
    assert reconciliation["patient_concentration_reconciles"] is True
