import pandas as pd


def utilization_summary(claims: pd.DataFrame) -> pd.DataFrame:
    dims = ["service_month", "service_category"]
    util = claims.groupby(dims).agg(
        claim_count=("claim_id", "count"),
        visits=("claim_id", "count"),
        unique_members=("member_id", "nunique"),
        member_months=("member_months", "max"),
        total_paid=("paid_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
    )
    util["claims_per_member"] = util["claim_count"] / util["unique_members"].replace(0, pd.NA)
    util["visits_per_1000_members"] = util["visits"] / util["member_months"] * 1000
    util["cost_per_visit"] = util["total_paid"] / util["visits"].replace(0, pd.NA)
    util["cost_per_member"] = util["total_paid"] / util["unique_members"].replace(0, pd.NA)
    util["pmpm"] = util["total_paid"] / util["member_months"]
    return util.reset_index()


def high_utilization_segments(claims: pd.DataFrame) -> pd.DataFrame:
    provider_service = claims.groupby(["provider_id", "provider_name", "service_category"]).agg(
        claim_count=("claim_id", "count"),
        unique_members=("member_id", "nunique"),
        total_paid=("paid_amount", "sum"),
        member_months=("member_months", "max"),
    )
    provider_service["visits_per_1000_members"] = provider_service["claim_count"] / provider_service["member_months"] * 1000
    provider_service["cost_per_visit"] = provider_service["total_paid"] / provider_service["claim_count"]
    return provider_service.sort_values("visits_per_1000_members", ascending=False).reset_index()
