from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.field_profiler import (  # noqa: E402
    build_profile_summary,
    calculate_field_availability,
    count_eobs_by_type,
    discover_provider_references,
    extract_diagnoses,
    extract_financial_adjudications,
    extract_service_codings,
    identify_adjudication_category_codes,
    identify_candidate_financial_amount_paths,
    identify_eob_claim_types,
    identify_service_date_range,
    list_nested_field_paths,
    list_top_level_fields,
    profile_arrays_and_objects,
    profile_resources,
    report_missing_fields,
    summarize_financial_adjudications,
    unknown_financial_codes,
)
from fhir.resource_loader import load_fhir_path  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button"


def _sample_eob() -> dict:
    return {
        "resourceType": "ExplanationOfBenefit",
        "id": "eob-1",
        "status": "active",
        "type": {"coding": [{"system": "claim-type-system", "code": "professional"}], "text": "Professional"},
        "billablePeriod": {"start": "2024-01-05", "end": "2024-01-07"},
        "provider": {"reference": "Practitioner/prv-1"},
        "insurer": {"reference": "Organization/payer-1"},
        "diagnosis": [
            {
                "sequence": 1,
                "diagnosisCodeableConcept": {"coding": [{"system": "icd-10", "code": "I10"}]},
            }
        ],
        "item": [
            {
                "sequence": 1,
                "servicedDate": "2024-01-06",
                "productOrService": {"coding": [{"system": "hcpcs", "code": "99213"}]},
                "adjudication": [
                    {
                        "category": {"coding": [{"system": "adjudication", "code": "submitted"}]},
                        "amount": {"value": 150.0, "currency": "USD"},
                    },
                    {
                        "category": {"coding": [{"system": "adjudication", "code": "paid"}]},
                        "amount": {"value": 70.0, "currency": "USD"},
                    },
                ],
            }
        ],
        "payment": {"amount": {"value": 70.0, "currency": "USD"}},
    }


def test_profile_bundle_containing_eob_resources():
    resources = [_sample_eob()]
    profile = profile_resources(resources, missing_field_paths=["id", "patient.reference"])

    assert profile.resource_counts == {"ExplanationOfBenefit": 1}
    assert profile.resource_ids == [{"resourceType": "ExplanationOfBenefit", "id": "eob-1"}]
    assert profile.eob_claim_types == ["Professional", "professional"]
    assert profile.adjudication_category_codes == ["paid", "submitted"]
    assert profile.earliest_service_date == "2024-01-05"
    assert profile.latest_service_date == "2024-01-07"
    assert profile.missing_field_counts["id"] == 0
    assert profile.missing_field_counts["patient.reference"] == 1


def test_nested_field_profiling_lists_arrays_objects_and_paths():
    resources = [
        {
            "resourceType": "Patient",
            "id": "patient-1",
            "address": [{"state": "MD", "postalCode": "21201"}],
        }
    ]

    paths = list_nested_field_paths(resources)
    arrays, objects = profile_arrays_and_objects(resources)

    assert list_top_level_fields(resources)["Patient"] == ["address", "id", "resourceType"]
    assert "address[]" in paths
    assert "address[].state" in paths
    assert "address" in arrays
    assert "address[]" in objects


def test_candidate_financial_amount_paths_are_observed_not_interpreted():
    candidates = identify_candidate_financial_amount_paths([_sample_eob()])

    assert "item[].adjudication[].amount.value" in candidates
    assert "payment.amount.value" in candidates


def test_service_date_range_is_none_when_absent():
    earliest, latest = identify_service_date_range([{"resourceType": "ExplanationOfBenefit", "id": "eob-no-date"}])

    assert earliest is None
    assert latest is None


def test_report_missing_fields_safely_handles_nested_absence():
    resources = [
        {"resourceType": "Coverage", "id": "cov-1", "period": {"start": "2024-01-01"}},
        {"resourceType": "Coverage", "status": "active"},
    ]

    missing = report_missing_fields(resources, ["id", "period.start", "period.end"])

    assert missing == {"id": 1, "period.start": 1, "period.end": 2}


def test_claim_type_and_adjudication_helpers_ignore_non_eob_resources():
    resources = [{"resourceType": "Patient", "id": "patient-1"}]

    assert identify_eob_claim_types(resources) == []
    assert identify_adjudication_category_codes(resources) == []


def test_cms_blue_button_fixture_has_multiple_eob_types():
    resources = load_fhir_path(FIXTURE_DIR)

    assert count_eobs_by_type(resources) == {"CARRIER": 1, "OUTPATIENT": 1, "PDE": 10}


def test_financial_amount_extraction_uses_adjudication_codes_not_position():
    resources = load_fhir_path(FIXTURE_DIR)
    summary = {row["adjudication_code"]: row for row in summarize_financial_adjudications(resources)}

    assert summary["CLM_LINE_SBMT_CHRG_AMT"]["proposed_analytical_meaning"] == "submitted amount"
    assert summary["CLM_LINE_ALOWD_CHRG_AMT"]["proposed_analytical_meaning"] == "allowed amount"
    assert summary["CLM_LINE_PRVDR_PMT_AMT"]["proposed_analytical_meaning"] == "provider paid amount"
    assert summary["CLM_LINE_SBMT_CHRG_AMT"]["claim_types_observed"] == "CARRIER|OUTPATIENT"
    assert summary["CLM_LINE_SBMT_CHRG_AMT"]["occurrence_count"] == 3


def test_multiple_codings_inside_adjudication_category_are_preserved():
    resources = load_fhir_path(FIXTURE_DIR)
    observations = extract_financial_adjudications(resources)
    submitted = [
        obs for obs in observations if any(coding["code"] == "CLM_LINE_SBMT_CHRG_AMT" for coding in obs.codings)
    ]

    assert any(len(obs.codings) > 1 for obs in submitted)
    assert any(
        {coding["code"] for coding in obs.codings}.issuperset({"submitted", "CLM_LINE_SBMT_CHRG_AMT"})
        for obs in submitted
    )


def test_missing_adjudication_arrays_are_handled_as_partial_financial_data():
    resources = load_fhir_path(FIXTURE_DIR)
    outpatient = [resource for resource in resources if resource.get("id") == "outpatient--local-synthetic-0001"][0]
    observations = extract_financial_adjudications([outpatient])

    assert len(outpatient["item"]) == 2
    assert all(obs.item_sequence == 1 for obs in observations)
    assert len(observations) == 4


def test_multiple_service_codings_are_extracted_with_system_display_and_version():
    resources = load_fhir_path(FIXTURE_DIR)
    service_codings = extract_service_codings(resources)
    carrier_99213 = [
        obs for obs in service_codings if obs.eob_type == "CARRIER" and obs.item_sequence == 1 and obs.code == "99213"
    ]

    assert len(carrier_99213) == 2
    assert {obs.system for obs in carrier_99213} == {
        "https://bluebutton.cms.gov/resources/codesystem/hcpcs",
        "http://www.ama-assn.org/go/cpt",
    }
    assert any(obs.version == "2024" for obs in carrier_99213)


def test_diagnosis_parsing_captures_sequence_system_code_and_type():
    resources = load_fhir_path(FIXTURE_DIR)
    diagnoses = extract_diagnoses(resources)

    assert {obs.code for obs in diagnoses} == {"E11.9", "I10", "R07.9"}
    principal = [obs for obs in diagnoses if obs.code == "I10"][0]
    assert principal.sequence == 1
    assert principal.system == "http://hl7.org/fhir/sid/icd-10-cm"
    assert principal.diagnosis_type == "principal"


def test_provider_reference_discovery_checks_provider_careteam_and_item_links():
    resources = load_fhir_path(FIXTURE_DIR)
    providers = discover_provider_references(resources)
    paths = {row["path"] for row in providers}

    assert "ExplanationOfBenefit.provider" in paths
    assert "ExplanationOfBenefit.careTeam[].provider" in paths
    assert "ExplanationOfBenefit.item[].careTeamSequence" in paths
    assert any(row["identifier_value"] == "1999999991" for row in providers)


def test_field_availability_calculation_varies_by_eob_type():
    resources = load_fhir_path(FIXTURE_DIR)
    rows = calculate_field_availability(resources)
    lookup = {(row["eob_type"], row["field"]): row for row in rows}

    assert lookup[("CARRIER", "allowed amount")]["populated_percentage"] == 1.0
    assert lookup[("PDE", "diagnosis")]["populated_percentage"] == 0.0
    assert lookup[("OUTPATIENT", "provider paid amount")]["populated_percentage"] == 0.0
    assert lookup[("OUTPATIENT", "covered paid amount")]["populated_percentage"] == 1.0


def test_unknown_adjudication_codes_are_reported():
    resources = load_fhir_path(FIXTURE_DIR)

    assert unknown_financial_codes(resources) == ["LOCAL_UNKNOWN_FINANCIAL_CODE"]


def test_profile_summary_is_derived_from_fixtures():
    resources = load_fhir_path(FIXTURE_DIR)
    summary = build_profile_summary(resources)

    assert summary["patient_resource_count"] == 1
    assert summary["coverage_resource_count"] == 4
    assert summary["eob_resource_count"] == 12
    assert summary["claim_line_count"] == 14
    assert summary["diagnosis_count"] == 3
    assert summary["percentage_items_with_hcpcs"] == 4 / 14
    assert summary["unknown_adjudication_code_count"] == 1
