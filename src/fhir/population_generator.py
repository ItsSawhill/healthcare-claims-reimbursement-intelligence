"""Build a multi-beneficiary synthetic FHIR population from labeled templates.

This module is used when live CMS sandbox extraction is unavailable. The output
is not presented as a real CMS population export; each resource carries
provenance tags that identify whether it was adapted from the official CMS
synthetic sample or from documentation-based local fixtures.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "fhir" / "cms_blue_button"
POPULATION_ROOT = ROOT / "data" / "raw" / "fhir" / "population"

OFFICIAL_SAMPLE_DATASET = "cms_blue_button_sample_bbuser29999_adapted"
LOCAL_FIXTURE_DATASET = "cms_blue_button_documentation_based_claim_fixtures_adapted"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_resources(path: Path) -> list[dict[str, Any]]:
    bundle = _read_json(path)
    return [entry["resource"] for entry in bundle.get("entry", [])]


def _tag(resource: dict[str, Any], *, source_type: str, source_dataset: str, alias: str) -> None:
    meta = resource.setdefault("meta", {})
    tags = meta.setdefault("tag", [])
    tags.extend(
        [
            {
                "system": "https://example.org/healthcare-claims/provenance-classification",
                "code": source_type,
                "display": source_type,
            },
            {
                "system": "https://example.org/healthcare-claims/source-dataset",
                "code": source_dataset,
                "display": source_dataset,
            },
            {
                "system": "https://example.org/healthcare-claims/beneficiary-alias",
                "code": alias,
                "display": alias,
            },
        ]
    )


def _shift_date(value: str | None, days: int) -> str | None:
    if not value:
        return value
    return (date.fromisoformat(value[:10]) + timedelta(days=days)).isoformat()


def _scale_amounts(resource: dict[str, Any], factor: float) -> None:
    for item in resource.get("item", []) or []:
        for adjudication in item.get("adjudication", []) or []:
            amount = adjudication.get("amount")
            if isinstance(amount, dict) and isinstance(amount.get("value"), (int, float)):
                amount["value"] = round(float(amount["value"]) * factor, 2)


def _rewrite_refs(resource: dict[str, Any], patient_id: str, coverage_map: dict[str, str]) -> None:
    resource["patient"] = {"reference": f"Patient/{patient_id}"}
    for insurance in resource.get("insurance", []) or []:
        coverage = insurance.get("coverage") or {}
        reference = coverage.get("reference")
        if reference:
            original = reference.split("/")[-1]
            coverage["reference"] = f"Coverage/{coverage_map.get(original, original)}"


def _make_patient(template: dict[str, Any], index: int) -> dict[str, Any]:
    patient = copy.deepcopy(template)
    patient_id = f"synthetic-beneficiary-{index:03d}"
    patient["id"] = patient_id
    patient["gender"] = "female" if index % 2 == 0 else "male"
    patient["birthDate"] = f"{1940 + (index % 35):04d}-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}"
    patient.pop("deceasedDateTime", None)
    patient["name"] = [{"use": "usual", "family": f"Synthetic{index:03d}", "given": ["FHIR"]}]
    patient["identifier"] = [
        {
            "system": "https://example.org/synthetic-beneficiary-alias",
            "value": patient_id,
        }
    ]
    patient["address"] = [{"use": "home", "state": f"{(index % 50) + 1:02d}", "postalCode": f"{90000 + index:05d}"}]
    _tag(patient, source_type="official_cms_synthetic", source_dataset=OFFICIAL_SAMPLE_DATASET, alias=patient_id)
    return patient


def _make_coverages(templates: list[dict[str, Any]], patient_id: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    output: list[dict[str, Any]] = []
    coverage_map: dict[str, str] = {}
    for template in templates:
        coverage = copy.deepcopy(template)
        original_id = coverage["id"]
        new_id = f"{original_id}--{patient_id}"
        coverage["id"] = new_id
        coverage["beneficiary"] = {"reference": f"Patient/{patient_id}"}
        if "subscriber" in coverage:
            coverage["subscriber"] = {"reference": f"Patient/{patient_id}"}
        coverage_map[original_id] = new_id
        _tag(coverage, source_type="official_cms_synthetic", source_dataset=OFFICIAL_SAMPLE_DATASET, alias=patient_id)
        output.append(coverage)
    return output, coverage_map


def _make_eob(template: dict[str, Any], patient_id: str, coverage_map: dict[str, str], index: int, sequence: int) -> dict[str, Any]:
    eob = copy.deepcopy(template)
    claim_type = (eob.get("type", {}).get("coding") or [{}])[0].get("code", "UNKNOWN")
    eob["id"] = f"{claim_type.lower()}--{patient_id}--{sequence:03d}"
    _rewrite_refs(eob, patient_id, coverage_map)
    shift_days = (index - 1) * 9 + sequence * 17
    if "billablePeriod" in eob:
        eob["billablePeriod"]["start"] = _shift_date(eob["billablePeriod"].get("start"), shift_days)
        eob["billablePeriod"]["end"] = _shift_date(eob["billablePeriod"].get("end"), shift_days)
    for item in eob.get("item", []) or []:
        if "servicedDate" in item:
            item["servicedDate"] = _shift_date(item["servicedDate"], shift_days)
        if "servicedPeriod" in item:
            item["servicedPeriod"]["start"] = _shift_date(item["servicedPeriod"].get("start"), shift_days)
            item["servicedPeriod"]["end"] = _shift_date(item["servicedPeriod"].get("end"), shift_days)
    factor = 0.75 + ((index + sequence) % 11) * 0.13
    _scale_amounts(eob, factor)
    for care_team in eob.get("careTeam", []) or []:
        provider = care_team.get("provider") or {}
        identifier = provider.get("identifier") or {}
        if identifier.get("value"):
            identifier["value"] = f"{int(identifier['value'][-7:]) + index * 37 + sequence:010d}"[-10:]
    provider = eob.get("provider", {}).get("identifier")
    if isinstance(provider, dict) and provider.get("value"):
        provider["value"] = f"{int(provider['value'][-7:]) + index * 41 + sequence:010d}"[-10:]
    source_type = "official_cms_synthetic" if claim_type == "PDE" else "documentation_based_fixture"
    source_dataset = OFFICIAL_SAMPLE_DATASET if claim_type == "PDE" else LOCAL_FIXTURE_DATASET
    _tag(eob, source_type=source_type, source_dataset=source_dataset, alias=patient_id)
    return eob


def build_population_bundle(beneficiary_count: int = 36) -> dict[str, Any]:
    """Return a FHIR Bundle containing a deterministic synthetic population."""
    patient_template = _read_json(FIXTURE_ROOT / "patient_bbuser29999.json")
    coverage_templates = _bundle_resources(FIXTURE_ROOT / "coverage_bundle_bbuser29999.json")
    pde_templates = _bundle_resources(FIXTURE_ROOT / "eob_bundle_bbuser29999.json")[:3]
    local_eob_templates = _bundle_resources(FIXTURE_ROOT / "local_documentation_based_eob_bundle.json")

    resources: list[dict[str, Any]] = []
    for index in range(1, beneficiary_count + 1):
        patient = _make_patient(patient_template, index)
        patient_id = patient["id"]
        coverages, coverage_map = _make_coverages(coverage_templates, patient_id)
        resources.append(patient)
        resources.extend(coverages)
        sequence = 1
        for template in pde_templates:
            resources.append(_make_eob(template, patient_id, coverage_map, index, sequence))
            sequence += 1
        resources.append(_make_eob(local_eob_templates[0], patient_id, coverage_map, index, sequence))
        sequence += 1
        if index % 2 == 0:
            resources.append(_make_eob(local_eob_templates[1], patient_id, coverage_map, index, sequence))

    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "resourceType": "Bundle",
        "id": "phase-4-synthetic-fhir-population",
        "type": "collection",
        "timestamp": timestamp,
        "entry": [{"resource": resource} for resource in resources],
    }


def write_population_bundle(output_path: str | Path, beneficiary_count: int = 36) -> Path:
    """Write the deterministic population Bundle and return its path."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_population_bundle(beneficiary_count)
    output.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return output


if __name__ == "__main__":
    write_population_bundle(POPULATION_ROOT / "phase4_synthetic_population_bundle.json")
