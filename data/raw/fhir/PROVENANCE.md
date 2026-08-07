# FHIR Fixture Provenance

## Downloaded CMS Synthetic Sample

Files:

- `tests/fixtures/fhir/cms_blue_button/patient_bbuser29999.json`
- `tests/fixtures/fhir/cms_blue_button/coverage_bundle_bbuser29999.json`
- `tests/fixtures/fhir/cms_blue_button/eob_bundle_bbuser29999.json`
- `tests/fixtures/fhir/cms_blue_button/readme.txt`

Source: CMS Blue Button API sample data zip linked from `https://bluebutton.cms.gov/api-documentation/explore-the-api/`.

Download/reference date: 2026-08-07.

Synthetic status: CMS publishes this as synthetic sample data for a single beneficiary test record. It must not be treated as real beneficiary data.

Modified: No content edits were made to the downloaded JSON files. The zip was extracted into the test fixture directory.

Intended use: Validate local FHIR loading and profiling against publicly supplied CMS Blue Button structures for Patient, Coverage, and ExplanationOfBenefit resources.

Known limitations: The downloaded EOB sample contains 10 PDE resources and does not cover Carrier, DME, HHA, Hospice, Inpatient, Outpatient, or SNF claim shapes. It is useful for Bundle loading, Patient/Coverage fields, PDE claim type handling, Part D product codes, and Part D adjudication codings.

## Local Documentation-Based Synthetic Fixtures

File:

- `tests/fixtures/fhir/cms_blue_button/local_documentation_based_eob_bundle.json`

Source basis:

- CMS Blue Button EOB documentation: `https://bluebutton.cms.gov/eob/`
- CMS Blue Button data overview: `https://bluebutton.cms.gov/data/understanding-the-data/`
- CMS Blue Button consuming-data guidance: `https://bluebutton.cms.gov/api-documentation/consuming-the-data/`
- CMS Blue Button adjudication code system: `https://bluebutton.cms.gov/fhir/CodeSystem/Adjudication/`

Creation/reference date: 2026-08-07.

Synthetic status: Locally constructed documentation-based fixture. It contains no real beneficiary, provider, or claim data.

Modified: Not applicable; this fixture was authored locally to supplement the downloaded sample.

Intended use: Exercise Carrier and Outpatient EOB shapes, HCPCS/CPT service coding, diagnosis parsing, provider references/identifiers, multiple claim lines, multiple adjudication categories, missing optional adjudication arrays, and unknown financial code handling.

Known limitations: This is representative, not authoritative. It should be replaced or supplemented with additional public CMS synthetic samples before production-like Bronze/Silver transformation rules are finalized.
