"""FHIR Bundle pagination helpers."""

from __future__ import annotations

from typing import Any


def get_next_link(bundle: dict[str, Any]) -> str | None:
    """Return the FHIR Bundle next link URL, if present."""
    links = bundle.get("link") or []
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and link.get("relation") == "next":
            url = link.get("url")
            return str(url) if url else None
    return None


def bundle_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract resource dictionaries from a Bundle without dropping malformed entries."""
    entries = bundle.get("entry") or []
    if not isinstance(entries, list):
        raise ValueError("FHIR Bundle.entry must be a list.")
    resources: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            raise ValueError(f"FHIR Bundle.entry[{index}] is missing a resource object.")
        resources.append(entry["resource"])
    return resources
