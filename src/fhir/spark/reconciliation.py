"""Gold/Silver reconciliation checks for FHIR analytics."""

from __future__ import annotations

from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def build_gold_reconciliation(silver: dict[str, DataFrame], gold: dict[str, DataFrame]) -> dict[str, Any]:
    """Compute reconciliation metrics between Silver inputs and Gold outputs."""
    header = silver["claim_header"]
    line = silver["claim_line"]
    financial = silver["claim_line_financial"]
    provider = silver["claim_provider"]

    claim_type_summary = gold["claim_type_summary"]
    financial_component = gold["financial_component_summary"]
    service_summary = gold["service_cost_summary"]
    provider_summary = gold["provider_reimbursement"]

    silver_claim_count = header.count()
    gold_claim_count = claim_type_summary.agg(F.sum("claim_count")).first()[0] or 0
    silver_line_count = line.count()
    gold_line_count = claim_type_summary.agg(F.sum("claim_line_count")).first()[0] or 0
    silver_financial_count = financial.count()
    gold_financial_count = financial_component.agg(F.sum("record_count")).first()[0] or 0
    service_count = service_summary.agg(F.sum("service_count")).first()[0] or 0
    silver_provider_groups = provider.join(
        silver["claim_header"].select("eob_id", "claim_type_code"),
        "eob_id",
        "left",
    ).select(
        "provider_identifier",
        "provider_reference",
        "provider_role_code",
        "provider_role_display",
        "provider_source",
        "claim_type_code",
    ).distinct().count()
    gold_provider_groups = provider_summary.select(
        "provider_identifier",
        "provider_reference",
        "provider_role_code",
        "provider_role_display",
        "provider_source",
        "claim_type_code",
    ).distinct().count()

    return {
        "silver_claim_header_count": silver_claim_count,
        "gold_claim_type_claim_count": int(gold_claim_count),
        "claim_counts_reconcile": silver_claim_count == gold_claim_count,
        "silver_claim_line_count": silver_line_count,
        "gold_claim_type_line_count": int(gold_line_count),
        "line_counts_reconcile": silver_line_count == gold_line_count,
        "silver_financial_record_count": silver_financial_count,
        "gold_financial_component_record_count": int(gold_financial_count),
        "financial_records_reconcile": silver_financial_count == gold_financial_count,
        "service_summary_service_count": int(service_count),
        "service_counts_reconcile": silver_line_count == service_count,
        "silver_provider_rows": provider.count(),
        "gold_provider_rows": provider_summary.count(),
        "silver_provider_group_count": silver_provider_groups,
        "gold_provider_group_count": gold_provider_groups,
        "provider_groups_reconcile": silver_provider_groups == gold_provider_groups,
        "provider_money_allocation_rule": (
            "Provider reimbursement allocates financial amounts only when an EOB has one provider attribution; "
            "multi-provider EOBs retain activity counts without multiplying dollars."
        ),
    }
