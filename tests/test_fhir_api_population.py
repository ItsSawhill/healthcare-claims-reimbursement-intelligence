from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fhir.api.blue_button_client import BlueButtonClient, BlueButtonClientConfig  # noqa: E402
from fhir.api.manifest import BeneficiaryManifestEntry, ExtractionManifest  # noqa: E402
from fhir.api.pagination import bundle_resources, get_next_link  # noqa: E402
from fhir.api.retry import retry_with_backoff  # noqa: E402
from fhir.population_generator import build_population_bundle  # noqa: E402


def test_pagination_finds_next_link_and_validates_entries():
    bundle = {
        "resourceType": "Bundle",
        "link": [{"relation": "self", "url": "one"}, {"relation": "next", "url": "two"}],
        "entry": [{"resource": {"resourceType": "Patient", "id": "p1"}}],
    }

    assert get_next_link(bundle) == "two"
    assert bundle_resources(bundle)[0]["id"] == "p1"

    with pytest.raises(ValueError):
        bundle_resources({"resourceType": "Bundle", "entry": [{"fullUrl": "missing-resource"}]})


def test_retry_with_backoff_retries_transient_errors(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr("time.sleep", lambda _: None)

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("temporary")
        return "ok"

    assert retry_with_backoff(flaky, attempts=3) == "ok"
    assert calls["count"] == 3


def test_extraction_manifest_supports_resume(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = ExtractionManifest(path)
    manifest.update(
        BeneficiaryManifestEntry(
            beneficiary_alias="beneficiary-001",
            source_dataset="cms_blue_button_sample",
            source_type="official_cms_synthetic",
            extraction_status="completed",
        )
    )
    manifest.write()

    loaded = ExtractionManifest(path)
    assert loaded.should_skip("beneficiary-001") is True
    assert loaded.should_skip("beneficiary-002") is False


def test_blue_button_client_redacts_authorization_header():
    redacted = BlueButtonClient.redact_headers({"Authorization": "Bearer placeholder", "Accept": "application/fhir+json"})

    assert redacted["Authorization"] == "<redacted>"
    assert "placeholder" not in str(redacted)


def test_population_generator_adds_provenance_and_multiple_beneficiaries():
    bundle = build_population_bundle(beneficiary_count=3)
    resources = [entry["resource"] for entry in bundle["entry"]]
    patients = [resource for resource in resources if resource["resourceType"] == "Patient"]
    eobs = [resource for resource in resources if resource["resourceType"] == "ExplanationOfBenefit"]

    assert len(patients) == 3
    assert len(eobs) > 3
    assert {tag["code"] for tag in resources[0]["meta"]["tag"]} & {"official_cms_synthetic", "documentation_based_fixture"}
