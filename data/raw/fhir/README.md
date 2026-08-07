# Raw FHIR Data

Place local synthetic FHIR JSON fixtures here for exploration.

Supported Phase 1 inputs:

- `Patient`
- `Coverage`
- `ExplanationOfBenefit`
- `Bundle` resources containing the supported resource types

The current FHIR utilities are local-only profiling helpers. They do not create
Bronze, Silver, or Gold tables and do not require Databricks.
