# FHIR Member Month Methodology

## Coverage Logic

Member months are derived from Silver `coverage` rows using `Coverage.period.start` and `Coverage.period.end`.

The Phase 4 Gold table `member_months` emits one active row per:

- `patient_id`
- `coverage_month`
- `coverage_type_code`

## Open-Ended Coverage

When `coverage_end` is missing, coverage is capped at the observed claim analysis window end date. The current analysis window is computed from Silver claim header service dates.

No artificial coverage end date is written back to Silver.

## Overlapping Coverage

Overlapping rows for the same `patient_id`, `coverage_month`, and `coverage_type_code` are de-duplicated so PMPM denominators do not double-count a beneficiary-month.

## PMPM Denominator

PMPM denominator counts distinct `patient_id + coverage_month` rows with active coverage.

## Limitations

The generated Phase 4 population uses adapted synthetic coverage records. Member-month logic is valid as an engineering method, but PMPM values are synthetic cohort metrics, not actuarial estimates.
