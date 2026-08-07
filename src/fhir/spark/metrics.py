"""Claim-type-aware reimbursement metric configuration for FHIR Gold tables."""

from __future__ import annotations


FINANCIAL_AMOUNT_COLUMNS = [
    "submitted_amount",
    "allowed_amount",
    "provider_paid_amount",
    "covered_paid_amount",
    "beneficiary_paid_amount",
    "deductible_amount",
    "coinsurance_amount",
    "noncovered_amount",
]

PDE_ANALYTICAL_CATEGORIES = {
    "part_d_plan_paid_amount": "total_part_d_plan_paid",
    "part_d_patient_paid_amount": "total_part_d_patient_paid",
    "part_d_total_drug_cost": "total_drug_cost",
}

CLAIM_TYPE_COST_BASIS = {
    "CARRIER": [
        ("provider_paid_amount", "provider_paid_amount"),
        ("allowed_amount", "allowed_amount"),
    ],
    "OUTPATIENT": [
        ("covered_paid_amount", "covered_paid_amount"),
        ("allowed_amount", "allowed_amount"),
    ],
    "PDE": [
        ("part_d_total_drug_cost", "part_d_total_drug_cost"),
        ("part_d_plan_paid_amount", "part_d_plan_paid_amount"),
    ],
}

CLAIM_TYPE_REIMBURSEMENT_RULES = {
    "CARRIER": {
        "submitted": "submitted_amount",
        "allowed": "allowed_amount",
        "paid": "provider_paid_amount",
        "notes": "Professional reimbursement uses provider-paid line adjudication when observed.",
    },
    "OUTPATIENT": {
        "submitted": "submitted_amount",
        "paid": "covered_paid_amount",
        "notes": "Observed outpatient fixture has covered paid amount, not provider-paid amount.",
    },
    "PDE": {
        "gross_cost": "part_d_total_drug_cost",
        "plan_paid": "part_d_plan_paid_amount",
        "patient_paid": "part_d_patient_paid_amount",
        "notes": "PDE Part D variables stay separate from professional/institutional payment fields.",
    },
}
