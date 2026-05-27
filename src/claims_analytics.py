import pandas as pd


def claims_summary(claims: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    grouped = claims.groupby(dimensions, dropna=False).agg(
        total_claims=("claim_id", "count"),
        denied_claims=("denial_flag", "sum"),
        total_billed=("billed_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        total_paid=("paid_amount", "sum"),
        member_responsibility=("member_responsibility", "sum"),
        unique_members=("member_id", "nunique"),
    )
    grouped["denial_rate"] = grouped["denied_claims"] / grouped["total_claims"]
    grouped["paid_to_billed_rate"] = grouped["total_paid"] / grouped["total_billed"].replace(0, pd.NA)
    return grouped.reset_index()


def monthly_trends(claims: pd.DataFrame) -> pd.DataFrame:
    monthly = claims.groupby("service_month").agg(
        total_claims=("claim_id", "count"),
        unique_members=("member_id", "nunique"),
        total_billed=("billed_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        total_paid=("paid_amount", "sum"),
        member_responsibility=("member_responsibility", "sum"),
        denied_claims=("denial_flag", "sum"),
        member_months=("member_months", "max"),
    )
    monthly["denial_rate"] = monthly["denied_claims"] / monthly["total_claims"]
    monthly["paid_per_claim"] = monthly["total_paid"] / monthly["total_claims"]
    monthly["pmpm"] = monthly["total_paid"] / monthly["member_months"]
    monthly["claims_per_1000_members"] = monthly["total_claims"] / monthly["member_months"] * 1000
    return monthly.reset_index()
