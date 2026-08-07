# FHIR Interview Findings

## Population-Level Findings

### Dataset Scale

- Beneficiaries: 36
- Bronze resources: 342
- EOBs: 162
- Claim lines: 216
- Diagnoses: 72
- Provider records: 198
- Financial records: 1368
- Unique service codes: 7
- Claim types:
- `CARRIER`: 36 claims
- `OUTPATIENT`: 18 claims
- `PDE`: 108 claims
- Service-code systems:
- `http://hl7.org/fhir/sid/ndc`: 108 claim lines
- `https://bluebutton.cms.gov/resources/codesystem/hcpcs`: 108 claim lines

The population bundle is synthetic. It combines resources adapted from the official CMS Blue Button synthetic sample with documentation-based claim-shape fixtures. It should not be interpreted as real Medicare utilization or spending.

### Spending Concentration

- Mean patient cost basis: $282.93
- Median patient cost basis: $253.24
- P90 patient cost basis: $441.74
- P95 patient cost basis: $475.54
- Top 10% spending share: 18.7%
- Top 20% spending share: 34.7%

Within this synthetic cohort of 36 beneficiaries, the top 10% accounted for 18.7% of the selected claim-type-aware cost basis. This describes the synthetic cohort and should not be interpreted as an estimate of Medicare population spending.

### Utilization

- Mean claims per beneficiary: 4.50
- Median claims per beneficiary: 4.00
- P90 claims per beneficiary: 5.00
- High-utilization threshold: 5.00 claims
- High-utilization beneficiaries: 18 (50.0%)
- Mean unique services per beneficiary: 6.00

High utilization is descriptive only. It is not labeled waste, abuse, fraud, or unnecessary care.

### PMPM

PMPM uses distinct active beneficiary-months from Coverage and keeps claim-type-specific numerators separate.

- 2015-10-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2015-11-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2015-12-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-01-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-02-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-03-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-04-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-05-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-06-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-07-01 `PDE`: members 36, drug PMPM 0.0, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-08-01 `PDE`: members 36, drug PMPM 1.4833333333333334, provider-paid PMPM 0.0, covered-paid PMPM 0.0
- 2016-09-01 `PDE`: members 36, drug PMPM 2.7666666666666666, provider-paid PMPM 0.0, covered-paid PMPM 0.0

No universal paid PMPM is created because professional, institutional, and Part D payment concepts are not interchangeable.

### Providers

- Provider population groups: 181
- Mean unique providers per beneficiary: 5.50

Provider financial attribution is reported only where a claim has one provider attribution. Multi-provider claims contribute activity and volume but do not multiply dollars.

### Claim Mix

- `CARRIER`: 36 claims
- `OUTPATIENT`: 18 claims
- `PDE`: 108 claims

### High-Cost Claims

- High-cost claim count: 10
- High-cost claim rate: 6.2%
- High-cost claims by type: {'CARRIER': 3, 'OUTPATIENT': 1, 'PDE': 6}

High-cost flags use within-claim-type percentiles and are not fraud or anomaly labels.

### FHIR Interoperability

- Financial mapping coverage: 1350/1368 records (98.7%)
- Quality metrics include numerator, denominator, and percentage by claim type in `fhir_data_quality_summary`.

### Engineering Findings

- Heterogeneous EOB shapes require typed financial components.
- Bronze preserves raw FHIR JSON and provenance.
- Silver normalizes patients, coverage, claims, lines, diagnoses, providers, and adjudication records.
- Gold adds semantic reimbursement tables, member months, PMPM, concentration, and provider population analytics.
- Unknown adjudication codes remain auditable.
- Spark reconciliation checks protect Bronze/Silver/Gold consistency.

### Top 10 Interview Findings

1. Across 36 synthetic beneficiaries, the top 10% accounted for 18.7% of the selected claim-type-aware cost basis. Source Gold table: patient_spending_concentration.
2. The top 20% accounted for 34.7% of selected cost basis, showing concentration within this synthetic cohort only. Source Gold table: patient_spending_concentration.
3. The cohort contains 162 EOBs and 216 claim lines across 3 claim types. Source Gold table: claim_type_summary.
4. Service vocabularies remain separate: {'http://hl7.org/fhir/sid/ndc': 108, 'https://bluebutton.cms.gov/resources/codesystem/hcpcs': 108}. Source Gold table: service_cost_summary.
5. 1350/1368 financial adjudication records have supported or candidate mappings. Source Gold table: financial_component_summary.
6. 10/162 claims are flagged high-cost using within-type percentiles, not anomaly labels. Source Gold table: high_cost_claims.
7. Mean claims per beneficiary is 4.50; high utilization is defined at the p90 threshold of 5 claims. Source Gold table: patient_utilization.
8. Provider population analytics cover 181 provider-role/source groups with double-count protected financial attribution. Source Gold table: provider_population_summary.
9. Member-month denominators include 4176 unique active beneficiary months. Source Gold table: member_months.
10. Provider attribution and service-code completeness are reported by claim type to show FHIR heterogeneity. Source Gold table: fhir_data_quality_summary.

### Reconciliation

```json
{
  "bronze_eob_count": 162,
  "bronze_eob_reconciles": true,
  "bronze_patient_count": 36,
  "bronze_patient_reconciles": true,
  "claim_header_line_item_sum": 216,
  "claim_lines_reconcile": true,
  "financial_records_reconcile": true,
  "gold_financial_summary_record_count": 1368,
  "gold_service_summary_count": 216,
  "high_cost_claim_population_count": 162,
  "high_cost_claim_total_cost_basis": 10185.52,
  "member_month_duplicate_patient_month_type_count": 0,
  "member_month_uniqueness_reconciles": true,
  "patient_concentration_reconciles": true,
  "patient_concentration_total_cost_basis": 10185.52,
  "pmpm_months_with_denominator": 46,
  "provider_attribution_rows": 198,
  "service_counts_reconcile": true,
  "silver_claim_header_count": 162,
  "silver_claim_line_count": 216,
  "silver_financial_record_count": 1368,
  "silver_patient_count": 36
}
```

### Limitations

- Automated CMS sandbox multi-beneficiary extraction requires OAuth credentials and was not run here.
- The generated population is adapted from synthetic templates; it is not a downloaded CMS population export.
- Carrier and Outpatient population records are documentation-based structural fixtures and are excluded from claims of official CMS population representativeness.
- Synthetic dates, providers, and amounts support engineering demonstration, not actuarial conclusions.
- The dataset is useful for pipeline and analytics design, but it is still not sufficient for credible ML anomaly modeling.
