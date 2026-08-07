# FHIR Cost Basis Methodology

FHIR EOB payment semantics differ by claim type. Phase 4 does not create a universal paid amount.

## Claim-Type Cost Basis

| Claim Type | Selected Cost Basis | FHIR / Adjudication Source | Reason | Comparable Across Claim Types |
|---|---|---|---|---|
| CARRIER | provider paid amount, fallback allowed amount | `CLM_LINE_PRVDR_PMT_AMT`, `CLM_LINE_ALOWD_CHRG_AMT` | Professional claims expose provider payment directly in the fixture | No |
| OUTPATIENT | covered paid amount, fallback allowed amount | `CLM_LINE_CVRD_PD_AMT`, `CLM_LINE_ALOWD_CHRG_AMT` | Institutional outpatient fixture exposes covered paid amount, not provider-paid | No |
| PDE | Part D total drug cost, fallback plan paid | `tot_rx_cst_amt`, `cvrd_d_plan_pd_amt` | PDE claims are pharmacy events with Part D-specific financial concepts | No |

## Coverage

Coverage percentage is measured in Gold quality outputs by claim type and field. Missing fields are not automatically errors because FHIR EOB structures are heterogeneous.

## Limitations

Cost basis supports within-claim-type ranking and synthetic cohort concentration. It should not be summed as universal healthcare spend without a separate normalization method.
