import numpy as np
import pandas as pd


def build_provider_kpis(claims: pd.DataFrame, reimbursement: pd.DataFrame) -> pd.DataFrame:
    provider = claims.groupby(["provider_id", "provider_name", "region"]).agg(
        total_claims=("claim_id", "count"),
        denied_claims=("denial_flag", "sum"),
        total_billed=("billed_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        total_paid=("paid_amount", "sum"),
        member_responsibility=("member_responsibility", "sum"),
        member_months=("member_months", "max"),
        unique_members=("member_id", "nunique"),
    )
    provider["average_cost_per_claim"] = provider["total_paid"] / provider["total_claims"]
    provider["reimbursement_rate"] = provider["total_paid"] / provider["total_billed"].replace(0, pd.NA)
    provider["allowed_rate"] = provider["total_allowed"] / provider["total_billed"].replace(0, pd.NA)
    provider["denial_rate"] = provider["denied_claims"] / provider["total_claims"]
    provider["pmpm_contribution"] = provider["total_paid"] / provider["member_months"]

    bench = reimbursement.groupby(["provider_id", "provider_name"]).agg(
        benchmark_variance_amount=("benchmark_variance_amount", "sum"),
        medicare_benchmark_total=("medicare_benchmark_total", "sum"),
    )
    provider = provider.reset_index().merge(bench.reset_index(), on=["provider_id", "provider_name"], how="left")
    provider["benchmark_variance_pct"] = (
        provider["benchmark_variance_amount"] / provider["medicare_benchmark_total"].replace(0, pd.NA)
    )

    provider["efficiency_score"] = (
        provider["average_cost_per_claim"].rank(pct=True) * 0.35
        + provider["denial_rate"].rank(pct=True) * 0.20
        + provider["pmpm_contribution"].rank(pct=True) * 0.25
        + provider["benchmark_variance_pct"].abs().rank(pct=True) * 0.20
    )
    provider["efficiency_rank"] = provider["efficiency_score"].rank(method="dense", ascending=True).astype(int)
    provider["financial_risk"] = np.select(
        [
            (provider["efficiency_score"] >= 0.75)
            | (provider["denial_rate"] >= 0.18)
            | (provider["benchmark_variance_pct"].abs() >= 0.30),
            provider["efficiency_score"] >= 0.55,
        ],
        ["High", "Medium"],
        default="Low",
    )
    return provider.sort_values(["financial_risk", "efficiency_score"], ascending=[True, False])
