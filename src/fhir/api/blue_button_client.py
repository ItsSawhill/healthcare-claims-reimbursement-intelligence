"""CMS Blue Button synthetic FHIR client.

The client is intentionally small and dependency-light. It supports live
synthetic sandbox calls when a caller supplies an OAuth token, and it is also
mockable for tests. No credentials are read from files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .pagination import get_next_link
from .retry import retry_with_backoff


FHIR_JSON = "application/fhir+json"


@dataclass(frozen=True)
class BlueButtonClientConfig:
    """Connection settings for a Blue Button FHIR endpoint."""

    base_url: str
    access_token: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 3


class BlueButtonClient:
    """Client for Patient, Coverage, and ExplanationOfBenefit resources."""

    def __init__(self, config: BlueButtonClientConfig):
        self.config = config

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": FHIR_JSON}
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        return headers

    @staticmethod
    def redact_headers(headers: dict[str, str]) -> dict[str, str]:
        """Return headers with secrets removed for safe logging."""
        return {key: ("<redacted>" if key.lower() == "authorization" else value) for key, value in headers.items()}

    def _get_json(self, url: str) -> dict[str, Any]:
        def request_once() -> dict[str, Any]:
            request = Request(url, headers=self._headers())
            try:
                with urlopen(request, timeout=self.config.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                raise ConnectionError(f"FHIR HTTP {exc.code} for {url}") from exc
            except URLError as exc:
                raise ConnectionError(f"FHIR request failed for {url}: {exc.reason}") from exc
            except json.JSONDecodeError as exc:
                raise ValueError(f"FHIR response was not valid JSON for {url}: {exc}") from exc

        return retry_with_backoff(request_once, attempts=self.config.max_retries)

    def search(self, resource_type: str, params: dict[str, str]) -> dict[str, Any]:
        """Run one FHIR search request."""
        query = urlencode(params)
        return self._get_json(f"{self.config.base_url.rstrip('/')}/{resource_type}?{query}")

    def search_all_pages(self, resource_type: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Run a FHIR search and follow Bundle next links."""
        resources: list[dict[str, Any]] = []
        bundle = self.search(resource_type, params)
        while True:
            entries = bundle.get("entry") or []
            for index, entry in enumerate(entries):
                resource = entry.get("resource") if isinstance(entry, dict) else None
                if not isinstance(resource, dict):
                    raise ValueError(f"{resource_type} Bundle.entry[{index}] missing resource object.")
                resources.append(resource)
            next_url = get_next_link(bundle)
            if not next_url:
                return resources
            bundle = self._get_json(next_url)

    def extract_beneficiary(self, beneficiary_id: str) -> dict[str, list[dict[str, Any]]]:
        """Extract Patient, Coverage, and EOB resources for one beneficiary."""
        patient = self.search_all_pages("Patient", {"_id": beneficiary_id})
        coverage = self.search_all_pages("Coverage", {"beneficiary": f"Patient/{beneficiary_id}"})
        eob = self.search_all_pages("ExplanationOfBenefit", {"patient": f"Patient/{beneficiary_id}"})
        return {"Patient": patient, "Coverage": coverage, "ExplanationOfBenefit": eob}
