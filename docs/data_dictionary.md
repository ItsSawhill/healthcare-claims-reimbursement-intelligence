# Data Dictionary

| Field | Description |
| --- | --- |
| claim_id | Unique claim identifier. |
| member_id | De-identified member identifier. |
| provider_id | Rendering or billing provider identifier. |
| provider_name | Provider display name for dashboard tables. |
| service_date | Date of service. |
| paid_date | Date the payer adjudicated or paid the claim. |
| diagnosis_code | Primary diagnosis code used for segmentation. |
| procedure_code | Procedure or CPT-style code used for service mix analysis. |
| service_category | Broad service category such as inpatient, outpatient, pharmacy, lab, or imaging. |
| billed_amount | Provider submitted charge. |
| allowed_amount | Contracted allowed amount after payer adjudication. |
| paid_amount | Payer paid amount after member responsibility and denials. |
| member_responsibility | Member cost share. |
| denial_flag | 1 when the claim was denied, otherwise 0. |
| region | Provider region. |
| payer | Payer or line of business. |
| member_months | Monthly eligibility denominator attached to claims in that service month. |
| medicare_benchmark_amount | Medicare-style benchmark amount used for reimbursement variance analysis. |
| benchmark_source | Indicates whether the benchmark came from the synthetic fallback or a local CMS benchmark file. |
