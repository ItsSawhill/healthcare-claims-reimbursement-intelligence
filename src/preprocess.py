import pandas as pd


REQUIRED_COLUMNS = {
    "claim_id",
    "member_id",
    "provider_id",
    "provider_name",
    "service_date",
    "paid_date",
    "diagnosis_code",
    "procedure_code",
    "service_category",
    "billed_amount",
    "allowed_amount",
    "paid_amount",
    "member_responsibility",
    "denial_flag",
    "region",
    "payer",
    "member_months",
    "medicare_benchmark_amount",
}


def clean_claims(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Claims file is missing required columns: {sorted(missing)}")

    claims = df.copy()
    claims["service_date"] = pd.to_datetime(claims["service_date"], errors="coerce")
    claims["paid_date"] = pd.to_datetime(claims["paid_date"], errors="coerce")
    claims = claims.dropna(subset=["claim_id", "member_id", "provider_id", "service_date"])
    claims = claims.drop_duplicates(subset=["claim_id"])

    amount_cols = [
        "billed_amount",
        "allowed_amount",
        "paid_amount",
        "member_responsibility",
        "member_months",
        "medicare_benchmark_amount",
    ]
    for col in amount_cols:
        claims[col] = pd.to_numeric(claims[col], errors="coerce").fillna(0).clip(lower=0)

    claims["denial_flag"] = claims["denial_flag"].fillna(0).astype(int).clip(0, 1)
    claims.loc[claims["denial_flag"].eq(1), "paid_amount"] = 0
    claims["allowed_amount"] = claims[["allowed_amount", "billed_amount"]].min(axis=1)
    claims["paid_amount"] = claims[["paid_amount", "allowed_amount"]].min(axis=1)
    claims["service_month"] = claims["service_date"].dt.to_period("M").dt.to_timestamp()
    claims["paid_month"] = claims["paid_date"].dt.to_period("M").dt.to_timestamp()
    claims["claim_count"] = 1
    claims["is_paid_claim"] = (claims["denial_flag"] == 0).astype(int)
    return claims
