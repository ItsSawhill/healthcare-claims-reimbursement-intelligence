# Existing Analytics Reuse for FHIR Gold

Phase 3 intentionally reuses analytical ideas from the flat-file pipeline, not the flat-file modules directly. The existing modules assume one normalized claim fact table with universal `paid_amount`, `allowed_amount`, `billed_amount`, PMPM denominators, provider names, and synthetic benchmark amounts. The FHIR Gold layer preserves claim-type-specific payment semantics instead.

| Module | Classification | Phase 3 Decision |
| --- | --- | --- |
| `claims_analytics.py` | reusable with adapter | Reused concepts: claim counts, dimensional summaries, monthly grouping. Not imported directly because FHIR has typed payment concepts. |
| `reimbursement.py` | reusable with adapter | Reused reimbursement aggregation concept, but implemented in Spark with separate provider-paid, covered-paid, and Part D fields. |
| `provider_kpis.py` | reusable with adapter | Provider activity counts are adapted. Risk scores are deferred because attribution and benchmarks are not complete. |
| `advanced_analytics.py` | future phase | Clustering and risk segmentation are not appropriate for the tiny one-patient FHIR sample. |
| `utilization.py` | reusable with adapter | Patient and service utilization counts are adapted. PMPM is deferred because member-month denominators are not yet normalized. |
| `anomaly_detection.py` | future phase | No ML or anomaly modeling in Phase 3. High-cost flags are descriptive only and within claim type. |
| `forecasting.py` | not appropriate for current FHIR sample | Sparse synthetic dates and 12 EOBs cannot support meaningful forecasting. |
| `scenario_simulation.py` | future phase | Contract/rate scenarios require stable paid/allowed definitions and larger samples. |
| `reporting.py` | reusable with adapter | Reporting pattern reused through `reports/fhir_interview_findings.md`, but content is FHIR-specific. |

Safe Phase 3 adaptations:

- claim counts
- line counts
- service/product summaries
- patient utilization counts
- provider activity summaries
- typed reimbursement component aggregations
- descriptive high-cost flags by claim type

Deferred:

- PMPM
- forecasting
- scenario simulation
- benchmark variance
- provider risk scoring
- ML anomaly models
