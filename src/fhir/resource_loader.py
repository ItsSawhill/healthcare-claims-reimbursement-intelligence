"""Local FHIR JSON loading helpers.

These utilities intentionally avoid Spark and Databricks dependencies. They are
for Phase 1 resource inspection only, before normalized Bronze/Silver/Gold
tables are implemented.
"""

from __future__ import annotations

import json
from collections import Counter
from json import JSONDecodeError
from pathlib import Path
from typing import Any


SUPPORTED_RESOURCE_TYPES = {"Patient", "Coverage", "ExplanationOfBenefit"}


class FHIRLoadError(ValueError):
    """Raised when a local FHIR JSON file or resource is invalid."""


FHIRResource = dict[str, Any]


def load_json_file(path: str | Path) -> FHIRResource:
    """Load a JSON object from disk with useful malformed JSON errors."""
    source_path = Path(path)
    try:
        with source_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except JSONDecodeError as exc:
        raise FHIRLoadError(f"Malformed JSON in {source_path}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc
    except OSError as exc:
        raise FHIRLoadError(f"Unable to read FHIR JSON file {source_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise FHIRLoadError(f"FHIR JSON file {source_path} must contain a JSON object.")
    return data


def validate_resource(resource: FHIRResource, *, allow_bundle: bool = False) -> FHIRResource:
    """Validate the minimum shape expected for a FHIR resource."""
    if not isinstance(resource, dict):
        raise FHIRLoadError("FHIR resource must be a JSON object.")

    resource_type = resource.get("resourceType")
    if not resource_type:
        raise FHIRLoadError("FHIR resource is missing required field: resourceType.")

    allowed_types = SUPPORTED_RESOURCE_TYPES | ({"Bundle"} if allow_bundle else set())
    if resource_type not in allowed_types:
        raise FHIRLoadError(
            f"Unsupported FHIR resourceType {resource_type!r}. Supported types: {sorted(allowed_types)}."
        )
    return resource


def load_resource(path: str | Path) -> FHIRResource:
    """Load one supported Patient, Coverage, or ExplanationOfBenefit resource."""
    return validate_resource(load_json_file(path), allow_bundle=False)


def load_bundle(path: str | Path) -> FHIRResource:
    """Load a FHIR Bundle resource from a local JSON file."""
    bundle = validate_resource(load_json_file(path), allow_bundle=True)
    if bundle["resourceType"] != "Bundle":
        raise FHIRLoadError(f"Expected resourceType 'Bundle', found {bundle['resourceType']!r}.")
    entries = bundle.get("entry", [])
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise FHIRLoadError("FHIR Bundle.entry must be an array when present.")
    return bundle


def extract_bundle_resources(bundle: FHIRResource) -> list[FHIRResource]:
    """Extract and validate supported resources from Bundle.entry.

    Invalid entries are raised with their bundle index so callers do not
    accidentally continue with silently discarded records.
    """
    validate_resource(bundle, allow_bundle=True)
    if bundle["resourceType"] != "Bundle":
        raise FHIRLoadError(f"Expected resourceType 'Bundle', found {bundle['resourceType']!r}.")

    entries = bundle.get("entry", [])
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise FHIRLoadError("FHIR Bundle.entry must be an array when present.")

    resources: list[FHIRResource] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise FHIRLoadError(f"FHIR Bundle.entry[{index}] must be a JSON object.")
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            raise FHIRLoadError(f"FHIR Bundle.entry[{index}].resource must be a JSON object.")
        try:
            resources.append(validate_resource(resource, allow_bundle=False))
        except FHIRLoadError as exc:
            raise FHIRLoadError(f"Invalid FHIR Bundle.entry[{index}].resource: {exc}") from exc
    return resources


def load_fhir_json(path: str | Path) -> list[FHIRResource]:
    """Load either a single supported resource or all supported resources in a Bundle."""
    data = load_json_file(path)
    resource_type = data.get("resourceType")
    if resource_type == "Bundle":
        return extract_bundle_resources(load_bundle(path))
    return [validate_resource(data, allow_bundle=False)]


def load_fhir_path(path: str | Path) -> list[FHIRResource]:
    """Load one FHIR JSON file or every JSON file directly under a directory."""
    source_path = Path(path)
    if source_path.is_dir():
        resources: list[FHIRResource] = []
        for json_path in sorted(source_path.glob("*.json")):
            resources.extend(load_fhir_json(json_path))
        return resources
    return load_fhir_json(source_path)


def count_by_resource_type(resources: list[FHIRResource]) -> dict[str, int]:
    """Count resources by resourceType."""
    return dict(Counter(resource.get("resourceType", "<missing>") for resource in resources))


def identify_resource_ids(resources: list[FHIRResource]) -> list[dict[str, str | None]]:
    """Return resourceType and id values, preserving missing IDs as None."""
    return [
        {
            "resourceType": resource.get("resourceType"),
            "id": resource.get("id"),
        }
        for resource in resources
    ]
