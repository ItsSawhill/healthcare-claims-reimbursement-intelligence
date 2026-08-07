# FHIR Financial Mapping

This report is based on the local Phase 1.5 fixture set:

- Downloaded CMS synthetic BBUser29999 Patient, Coverage, and PDE ExplanationOfBenefit examples.
- Locally constructed documentation-based Carrier and Outpatient EOB examples.

Financial values are mapped by `ExplanationOfBenefit.item[].adjudication[].category.coding[]` code, not by array position. CARIN codings are retained when observed, but CMS-specific adjudication codes drive analytical mapping decisions.

## Observed Financial Codes

| adjudication code | description if known | exact observed FHIR path | claim types observed | occurrences | amount coverage | proposed analytical meaning | mapping status | notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `CLM_LINE_SBMT_CHRG_AMT` | Line Submitted Charge Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER, OUTPATIENT | 3 | 100% | submitted amount | confirmed | CARIN `submitted` coding coexists on one Carrier line. |
| `CLM_LINE_ALOWD_CHRG_AMT` | Line Allowed Charge Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER | 2 | 100% | allowed amount | confirmed | CARIN `eligible` coding coexists on one Carrier line. |
| `CLM_LINE_PRVDR_PMT_AMT` | Line Provider Payment Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER | 2 | 100% | provider paid amount | confirmed | Best current line-level paid amount for professional-style provider reimbursement analytics. |
| `CLM_LINE_BENE_PMT_AMT` | Line Paid By Beneficiary Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER | 1 | 100% | beneficiary paid amount | confirmed | Do not combine with deductible/coinsurance until a patient-responsibility business definition is chosen. |
| `CLM_LINE_CVRD_PD_AMT` | Payment Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | OUTPATIENT | 1 | 100% | covered paid amount | confirmed | Distinct from provider payment amount in observed fixture. |
| `CLM_LINE_MDCR_DDCTBL_AMT` | Cash Deductible Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER | 1 | 100% | deductible | confirmed | Candidate component of patient responsibility. |
| `CLM_LINE_MDCR_COINSRNC_AMT` | Coinsurance Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | OUTPATIENT | 1 | 100% | coinsurance | confirmed | Candidate component of patient responsibility. |
| `CLM_LINE_NCVRD_CHRG_AMT` | Non-Covered Charge Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | CARRIER | 1 | 100% | non-covered charge | confirmed | Keep separate from beneficiary paid amount. |
| `https://bluebutton.cms.gov/resources/variables/cvrd_d_plan_pd_amt` | Amount paid by Part D plan for the PDE | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | Part D plan paid amount | confirmed | Downloaded CMS sample uses URI-like variable code values for PDE adjudication. |
| `https://bluebutton.cms.gov/resources/variables/ptnt_pay_amt` | Amount Paid by Patient | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | Part D patient paid amount | confirmed | CARIN `paidbypatient` coding coexists. |
| `https://bluebutton.cms.gov/resources/variables/tot_rx_cst_amt` | Total drug cost | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | Part D total drug cost | confirmed | CARIN `drugcost` coding coexists. |
| `https://bluebutton.cms.gov/resources/variables/gdc_abv_oopt_amt` | Gross Drug Cost Above Part D Out-of-Pocket Threshold | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | Keep as separate Part D concept. CARIN `coinsurance` also appears, but do not collapse into medical coinsurance. |
| `https://bluebutton.cms.gov/resources/variables/gdc_blw_oopt_amt` | Gross Drug Cost Below Part D Out-of-Pocket Threshold | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | Keep as separate Part D concept. CARIN `coinsurance` also appears. |
| `https://bluebutton.cms.gov/resources/variables/lics_amt` | Low Income Cost Sharing Subsidy Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | Subsidy amount, not direct provider reimbursement. |
| `https://bluebutton.cms.gov/resources/variables/othr_troop_amt` | Other True Out-of-Pocket Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | CARIN `priorpayerpaid` coding coexists. |
| `https://bluebutton.cms.gov/resources/variables/plro_amt` | Patient Liability Reduction Other Paid Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | CARIN `priorpayerpaid` coding coexists. |
| `https://bluebutton.cms.gov/resources/variables/rptd_gap_dscnt_num` | Gap Discount Amount | `ExplanationOfBenefit.item[].adjudication[].amount.value` | PDE | 10 | 100% | none yet | candidate | CARIN `discount` coding coexists. |
| `LOCAL_UNKNOWN_FINANCIAL_CODE` | unknown | `ExplanationOfBenefit.item[].adjudication[].amount.value` | OUTPATIENT | 1 | 100% | none | unsupported | Synthetic unknown code included to validate unknown-code reporting. |

## Mapping Guidance

Use line-level CMS adjudication codes for submitted, allowed, provider paid, covered paid, beneficiary paid, deductible, coinsurance, and non-covered charge fields. Do not combine CMS financial concepts unless the target business metric explicitly defines the rollup.

For provider KPI analytics, `CLM_LINE_PRVDR_PMT_AMT` is the clearest observed provider-paid line amount for Carrier-style claims. `CLM_LINE_CVRD_PD_AMT` is observed as covered paid amount for an Outpatient-style fixture and should remain separate until additional institutional EOB samples confirm whether it is the right paid amount for those claim types.

For Part D PDE resources, downloaded CMS synthetic data uses CMS variable URI codes and NDC product codes rather than HCPCS. PDE amounts should be profiled separately from medical claims before being merged into reimbursement analytics.
