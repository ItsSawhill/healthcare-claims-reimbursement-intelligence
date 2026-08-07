# FHIR Interview Findings

## Dataset Profile

- Bronze resources: 17
- EOB count: 12
- Claim lines: 14
- Provider records: 13
- Financial records: 103
- Date coverage: 2015-06-01 to 2024-04-03

## Claim Mix

- `CARRIER`: 1 claims, 2 lines, 9 financial records.
- `OUTPATIENT`: 1 claims, 2 lines, 4 financial records.
- `PDE`: 10 claims, 10 lines, 90 financial records.

## Financial Findings

- `CARRIER`: submitted $255.00; allowed $140.00; provider paid $112.00; covered paid $0.00; beneficiary paid $19.00; Part D plan paid $0.00; drug cost $0.00.
- `OUTPATIENT`: submitted $220.00; allowed $0.00; provider paid $0.00; covered paid $118.00; beneficiary paid $0.00; Part D plan paid $0.00; drug cost $0.00.
- `PDE`: submitted $0.00; allowed $0.00; provider paid $0.00; covered paid $0.00; beneficiary paid $0.00; Part D plan paid $140.00; drug cost $210.00.

These amounts are intentionally not collapsed into one universal paid amount. Provider-paid, covered-paid, and Part D concepts remain separate.

## Service Findings

- Unique service/product codes: 13
- Service code systems: {'http://hl7.org/fhir/sid/ndc': 10, 'https://bluebutton.cms.gov/resources/codesystem/hcpcs': 4}
- HCPCS/CPT and NDC product vocabularies are preserved separately.

## Provider Findings

- Provider records: 13
- Provider source distribution: {'careTeam.provider': 12, 'ExplanationOfBenefit.provider.reference': 1}
- Provider role distribution: {'prescribing': 10, 'performing': 1, 'referring': 1, 'unlabeled': 1}
- Provider reimbursement dollars are allocated only when a claim has one provider attribution. Multi-provider claims retain activity counts without multiplying reimbursement amounts.

## High-Cost Findings

- High-cost claims using within-claim-type percentiles: 3
- `outpatient--local-synthetic-0001` (OUTPATIENT): covered_paid_amount = $118.00.
- `carrier--local-synthetic-0001` (CARRIER): provider_paid_amount = $112.00.
- `pde--1652397328` (PDE): part_d_total_drug_cost = $100.00.

## FHIR Interoperability Findings

- EOBs with provider attribution: 100.0%
- EOBs with diagnosis: 16.7%
- Claim lines with service codes: 100.0%
- Claim lines with financial data: 92.9%
- Unsupported adjudication code records: 1 of 103

## Engineering Findings

- EOB shapes are heterogeneous across PDE, Carrier, and Outpatient examples.
- Financial adjudication arrays were normalized into a typed component table before business aggregation.
- Raw FHIR JSON remains preserved in Bronze for auditability and remapping.
- Unknown adjudication codes are retained rather than discarded.

## Reconciliation

- Claim counts reconcile: True
- Line counts reconcile: True
- Financial records reconcile: True
- Provider attribution groups reconcile: True

## Limitations

- Patient resource count is 1; patient concentration findings are not meaningful.
- The fixture set contains 12 EOBs and is not population-scale.
- The downloaded CMS sample is mainly PDE; Carrier and Outpatient resources are documentation-based synthetic fixtures.
- Dates are sparse and synthetic, so monthly output should not be interpreted as a real utilization trend.
- Unsupported claim types remain future work.
- This is an engineering demonstration, not a clinical or actuarial conclusion.
