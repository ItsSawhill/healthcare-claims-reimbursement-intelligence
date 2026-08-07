# FHIR Population Data Source Assessment

Assessment date: 2026-08-07

## Sources Investigated

| Source | Organization | Type | Acquisition Method | Beneficiaries Available Here | FHIR Version | EOB Availability | Coverage Availability | Provider Availability | Reimbursement Fields | Suitability |
|---|---|---:|---|---:|---|---|---|---|---|---|
| CMS Blue Button sandbox synthetic users | CMS | official_cms_synthetic | OAuth-protected sandbox API | 0 live users extracted | R4-style Blue Button API examples | Yes, via API when authorized | Yes | Yes | CMS adjudication extensions | Best target source, but not available without OAuth tokens |
| CMS Blue Button published sample bundle | CMS | official_cms_synthetic | Existing local downloaded sample fixture | 1 beneficiary template | R4-style Blue Button sample | Yes, mostly PDE | Yes | Yes | CMS adjudication codes and Part D variables | Strong structural source, insufficient as an unmodified population |
| Synthea FHIR | MITRE / Synthea project | external_synthetic | Not present locally; not downloaded in this environment | 0 | R4 exports vary by generator settings | Not guaranteed to include CMS Blue Button EOB adjudication semantics | Often includes Coverage | Varies | Less aligned with CMS Blue Button reimbursement adjudication | Useful future source, but less direct for Blue Button reimbursement mappings |
| Local documentation-based EOB fixtures | Project fixtures | documentation_based_fixture | Existing local fixtures | Structural only | R4-style EOB | Carrier and Outpatient examples | Linked to sample coverage | Yes | CMS-style adjudication code examples | Suitable for parser and claim-type edge cases, not primary population evidence |

## Selected `PRIMARY_POPULATION_SOURCE`

`cms_blue_button_sample_bbuser29999_adapted_population`

Rationale:

- The official CMS Blue Button synthetic sample is the only available local source with observed CMS adjudication codes and Part D financial variables.
- Live CMS sandbox extraction was not attempted because OAuth credentials are required and no tokens or beneficiary credentials should be committed.
- Synthea was not available locally and would not guarantee the CMS Blue Button adjudication structure needed for this reimbursement pipeline.
- The generated Phase 4 population is therefore explicitly labeled as an adapted synthetic engineering dataset. It is not presented as a downloaded CMS multi-beneficiary population.

## Final Classification

- Patient, Coverage, and PDE resources adapted from the CMS Blue Button synthetic sample: `official_cms_synthetic`
- Carrier and Outpatient resources adapted from local documentation-based fixtures: `documentation_based_fixture`
- No resources are classified as `external_synthetic` in this run.

## Suitability

- Reimbursement analytics: suitable for demonstrating claim-type-aware transformations and aggregation.
- PMPM: suitable for methodology demonstration because Coverage periods are present; not suitable for actuarial conclusions.
- Utilization analysis: suitable for synthetic cohort distribution examples.
- Provider analysis: suitable for demonstrating double-count-protected attribution.
- Spending concentration: suitable for demonstrating cohort-level concentration mechanics.

## Important Limitations

- This is not a true multi-beneficiary CMS sandbox extraction.
- Synthetic beneficiaries, dates, providers, and amounts were deterministically varied from templates.
- Locally constructed documentation-based fixtures are included for Carrier and Outpatient diversity.
- Findings must be described as synthetic cohort findings only.
