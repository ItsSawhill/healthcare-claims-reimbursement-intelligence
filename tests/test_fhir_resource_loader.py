import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.resource_loader import (  # noqa: E402
    FHIRLoadError,
    count_by_resource_type,
    extract_bundle_resources,
    identify_resource_ids,
    load_bundle,
    load_fhir_json,
    load_fhir_path,
    load_resource,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_single_patient_resource(tmp_path):
    patient_path = _write_json(
        tmp_path / "patient.json",
        {
            "resourceType": "Patient",
            "id": "patient-1",
            "gender": "female",
            "birthDate": "1975-01-15",
        },
    )

    resource = load_resource(patient_path)
    resources = load_fhir_json(patient_path)

    assert resource["resourceType"] == "Patient"
    assert resources == [resource]
    assert identify_resource_ids(resources) == [{"resourceType": "Patient", "id": "patient-1"}]


def test_load_bundle_containing_coverage_resources(tmp_path):
    bundle_path = _write_json(
        tmp_path / "coverage_bundle.json",
        {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Coverage", "id": "cov-1", "status": "active"}},
                {"resource": {"resourceType": "Coverage", "id": "cov-2", "status": "cancelled"}},
            ],
        },
    )

    bundle = load_bundle(bundle_path)
    resources = extract_bundle_resources(bundle)

    assert count_by_resource_type(resources) == {"Coverage": 2}
    assert identify_resource_ids(resources) == [
        {"resourceType": "Coverage", "id": "cov-1"},
        {"resourceType": "Coverage", "id": "cov-2"},
    ]


def test_load_empty_bundle(tmp_path):
    bundle_path = _write_json(tmp_path / "empty_bundle.json", {"resourceType": "Bundle", "entry": []})

    assert load_fhir_json(bundle_path) == []


def test_missing_resource_type_fails(tmp_path):
    resource_path = _write_json(tmp_path / "missing_type.json", {"id": "no-type"})

    with pytest.raises(FHIRLoadError, match="resourceType"):
        load_resource(resource_path)


def test_missing_resource_id_is_reported_not_rejected(tmp_path):
    resource_path = _write_json(tmp_path / "missing_id.json", {"resourceType": "Patient", "gender": "male"})

    resources = load_fhir_json(resource_path)

    assert identify_resource_ids(resources) == [{"resourceType": "Patient", "id": None}]


def test_malformed_bundle_entry_fails_with_index(tmp_path):
    bundle_path = _write_json(
        tmp_path / "bad_bundle.json",
        {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "patient-1"}},
                {"fullUrl": "urn:uuid:bad-entry"},
            ],
        },
    )

    with pytest.raises(FHIRLoadError, match=r"entry\[1\].resource"):
        load_fhir_json(bundle_path)


def test_malformed_json_has_useful_error(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"resourceType": "Patient",', encoding="utf-8")

    with pytest.raises(FHIRLoadError, match="Malformed JSON"):
        load_resource(bad_path)


def test_load_fhir_path_loads_directory_json_files(tmp_path):
    _write_json(tmp_path / "patient.json", {"resourceType": "Patient", "id": "patient-1"})
    _write_json(
        tmp_path / "bundle.json",
        {
            "resourceType": "Bundle",
            "entry": [{"resource": {"resourceType": "Coverage", "id": "cov-1"}}],
        },
    )
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    resources = load_fhir_path(tmp_path)

    assert count_by_resource_type(resources) == {"Coverage": 1, "Patient": 1}
