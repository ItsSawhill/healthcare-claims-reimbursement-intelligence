"""Extract or prepare synthetic FHIR population resources.

This script does not require live CMS access by default. In fixture mode it
creates a deterministic, provenance-labeled population Bundle from the existing
synthetic CMS Blue Button sample and documentation-based structural fixtures.
Live sandbox extraction requires an OAuth token supplied through the environment
variable named in the config file.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fhir.api.blue_button_client import BlueButtonClient, BlueButtonClientConfig
from fhir.api.manifest import BeneficiaryManifestEntry, ExtractionManifest
from fhir.population_generator import write_population_bundle


def _fixture_mode(output_dir: Path, beneficiary_count: int) -> Path:
    return write_population_bundle(output_dir / "phase4_synthetic_population_bundle.json", beneficiary_count)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare synthetic Blue Button-style FHIR population data.")
    parser.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    parser.add_argument("--base-url", default="https://sandbox.bluebutton.cms.gov/v2/fhir")
    parser.add_argument("--token-env", default="BLUE_BUTTON_ACCESS_TOKEN")
    parser.add_argument("--beneficiary-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "raw" / "fhir" / "population")
    parser.add_argument("--manifest-path", type=Path, default=ROOT / "outputs" / "metrics" / "blue_button_extraction_manifest.json")
    parser.add_argument("--beneficiary-count", type=int, default=36)
    args = parser.parse_args()

    if args.mode == "fixture":
        output = _fixture_mode(args.output_dir, args.beneficiary_count)
        print(f"Wrote fixture-mode synthetic population Bundle: {output}")
        return 0

    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"Missing OAuth token environment variable {args.token_env}; use fixture mode or provide a token.")
    if not args.beneficiary_id:
        raise SystemExit("Live mode requires at least one --beneficiary-id.")

    client = BlueButtonClient(BlueButtonClientConfig(base_url=args.base_url, access_token=token))
    manifest = ExtractionManifest(args.manifest_path)
    for beneficiary_id in args.beneficiary_id:
        alias = f"cms-sandbox-{beneficiary_id}"
        if manifest.should_skip(alias):
            continue
        try:
            extracted = client.extract_beneficiary(beneficiary_id)
            manifest.update(
                BeneficiaryManifestEntry(
                    beneficiary_alias=alias,
                    source_dataset="cms_blue_button_sandbox",
                    source_type="official_cms_synthetic",
                    extraction_status="completed",
                    patient_resource_count=len(extracted["Patient"]),
                    coverage_count=len(extracted["Coverage"]),
                    eob_count=len(extracted["ExplanationOfBenefit"]),
                )
            )
        except Exception as exc:
            manifest.update(
                BeneficiaryManifestEntry(
                    beneficiary_alias=alias,
                    source_dataset="cms_blue_button_sandbox",
                    source_type="official_cms_synthetic",
                    extraction_status="failed",
                    error=str(exc),
                )
            )
    manifest.write()
    print(f"Wrote live extraction manifest: {args.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
