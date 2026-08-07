"""Extraction manifest support for resumable synthetic FHIR acquisition."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BeneficiaryManifestEntry:
    """One beneficiary extraction status record."""

    beneficiary_alias: str
    source_dataset: str
    source_type: str
    extraction_status: str
    patient_resource_count: int = 0
    coverage_count: int = 0
    eob_count: int = 0
    error: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExtractionManifest:
    """JSON-backed manifest used to resume beneficiary extraction."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.entries: dict[str, BeneficiaryManifestEntry] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("beneficiaries", []):
                entry = BeneficiaryManifestEntry(**item)
                self.entries[entry.beneficiary_alias] = entry

    def should_skip(self, beneficiary_alias: str) -> bool:
        """Return True when the beneficiary previously completed extraction."""
        entry = self.entries.get(beneficiary_alias)
        return bool(entry and entry.extraction_status == "completed")

    def update(self, entry: BeneficiaryManifestEntry) -> None:
        """Update an entry in memory."""
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self.entries[entry.beneficiary_alias] = entry

    def write(self) -> None:
        """Persist the manifest to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "beneficiaries": [asdict(entry) for entry in sorted(self.entries.values(), key=lambda item: item.beneficiary_alias)],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
