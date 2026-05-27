# Business Case

## Scenario

A regional health plan is preparing for an annual provider contract review cycle. Leadership has observed rising paid claims expense and uneven PMPM movement across service categories, but the existing reporting process is fragmented across claims extracts, spreadsheet summaries, and ad hoc reimbursement analyses.

The reimbursement strategy team needs a repeatable analytics workflow that can identify cost drivers, benchmark reimbursement against Medicare-style expectations, flag operational risk, and provide leadership with a concise executive narrative.

This project simulates that workflow using de-identified synthetic claims data and dashboard-ready outputs.

## Stakeholder Users

| Stakeholder | Primary Questions |
| --- | --- |
| Chief Financial Officer | Are medical costs and PMPM moving within budget expectations? |
| VP of Network Management | Which providers should be prioritized for contract review? |
| Reimbursement Analyst | Which provider-service-payer combinations are above benchmark? |
| Utilization Management Lead | Which service categories show high utilization or cost per visit? |
| Claims Operations Manager | Which providers or lines of business have elevated denial rates? |
| Business Information Consultant | How can claims, utilization, reimbursement, and anomaly outputs be packaged for leadership? |

## Business Questions

1. Which providers are driving the largest share of paid claims?
2. Which providers have high denial rates, high PMPM contribution, or high benchmark variance?
3. Are reimbursement rates materially above or below Medicare-style benchmarks?
4. Which service categories are driving utilization intensity?
5. Are there claim, provider, or monthly trend anomalies that require review?
6. What is the next-month forecast for paid amount, claim volume, and PMPM?
7. Which operational interventions should leadership prioritize?

## Analytics Approach

The pipeline creates a clean claims table, then produces multiple analytic views:

- monthly paid amount, allowed amount, claim count, PMPM, and denial trends
- provider KPI table with reimbursement, utilization, benchmark, and risk fields
- reimbursement benchmarking by provider, service category, payer, and region
- utilization metrics including visits per 1,000 members and cost per visit
- cost driver analysis by service category, provider, and payer
- provider segmentation using clustering
- anomaly candidate extraction using z-score, IQR, and business thresholds
- baseline forecasts for paid amount, claim volume, and PMPM

## Recommended Actions

1. Prioritize providers in the Critical and High provider risk tiers for reimbursement and contracting review.
2. Review provider-service-payer combinations more than 20% above benchmark for coding mix, contract terms, and medical necessity.
3. Audit denial-risk providers for authorization, eligibility, documentation, and coding workflow issues.
4. Monitor PMPM and visits per 1,000 members monthly to separate utilization-driven cost increases from reimbursement-driven cost increases.
5. Use the anomaly output as a review queue for claims operations and reimbursement analysts.
6. Refresh the dashboard and Excel workbook during monthly close so leadership receives consistent reporting.

## Expected Business Impact

This project does not claim realized savings because it uses synthetic data. In a real payer or provider environment, the same workflow would support:

- faster monthly reimbursement reporting
- better provider contract prioritization
- earlier detection of denial and reimbursement outliers
- improved executive visibility into PMPM and medical cost trends
- repeatable dashboard and Excel deliverables for finance, network, and operations teams
