import numpy as np
import pandas as pd


def reimbursement_benchmarking(claims: pd.DataFrame) -> pd.DataFrame:
    grouped = claims.groupby(["provider_id", "provider_name", "service_category", "region", "payer"]).agg(
        total_claims=("claim_id", "count"),
        total_billed=("billed_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        total_paid=("paid_amount", "sum"),
        medicare_benchmark_total=("medicare_benchmark_amount", "sum"),
    )
    grouped["paid_to_billed_rate"] = grouped["total_paid"] / grouped["total_billed"].replace(0, pd.NA)
    grouped["allowed_to_billed_rate"] = grouped["total_allowed"] / grouped["total_billed"].replace(0, pd.NA)
    grouped["benchmark_variance_amount"] = grouped["total_allowed"] - grouped["medicare_benchmark_total"]
    grouped["benchmark_variance_pct"] = grouped["benchmark_variance_amount"] / grouped["medicare_benchmark_total"].replace(0, pd.NA)
    grouped["benchmark_flag"] = np.select(
        [grouped["benchmark_variance_pct"] > 0.20, grouped["benchmark_variance_pct"] < -0.20],
        ["Above benchmark", "Below benchmark"],
        default="In range",
    )
    return grouped.reset_index().sort_values("benchmark_variance_amount", ascending=False)


def reimbursement_monthly(claims: pd.DataFrame) -> pd.DataFrame:
    monthly = claims.groupby(["service_month", "provider_id", "provider_name"]).agg(
        total_billed=("billed_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        total_paid=("paid_amount", "sum"),
        total_claims=("claim_id", "count"),
    )
    monthly["paid_to_billed_rate"] = monthly["total_paid"] / monthly["total_billed"].replace(0, pd.NA)
    monthly["allowed_to_billed_rate"] = monthly["total_allowed"] / monthly["total_billed"].replace(0, pd.NA)
    return monthly.reset_index()
