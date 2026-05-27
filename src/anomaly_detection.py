import numpy as np
import pandas as pd


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(0, index=series.index)
    return (series - series.mean()) / std


def _iqr_flag(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    return (series < q1 - multiplier * iqr) | (series > q3 + multiplier * iqr)


def detect_anomalies(claims: pd.DataFrame, provider_kpis: pd.DataFrame, monthly_trends: pd.DataFrame) -> pd.DataFrame:
    records = []

    claim_sample = claims.copy()
    claim_sample["billed_zscore"] = _zscore(claim_sample["billed_amount"])
    high_claims = claim_sample[(claim_sample["billed_zscore"] > 4) | _iqr_flag(claim_sample["billed_amount"], 3.0)]
    for row in high_claims.nlargest(150, "billed_amount").itertuples(index=False):
        records.append(
            {
                "anomaly_type": "High billed claim",
                "entity_type": "claim",
                "entity_id": row.claim_id,
                "service_month": row.service_month,
                "metric": "billed_amount",
                "metric_value": row.billed_amount,
                "severity": "High" if row.billed_zscore > 5 else "Medium",
                "rationale": f"Claim billed amount z-score {row.billed_zscore:.2f}.",
            }
        )

    provider = provider_kpis.copy()
    provider["denial_zscore"] = _zscore(provider["denial_rate"])
    provider_flags = provider[
        (provider["denial_zscore"] > 2)
        | (provider["benchmark_variance_pct"].abs() > 0.25)
        | (provider["financial_risk"] == "High")
    ]
    for row in provider_flags.itertuples(index=False):
        records.append(
            {
                "anomaly_type": "Provider financial risk",
                "entity_type": "provider",
                "entity_id": row.provider_id,
                "service_month": pd.NaT,
                "metric": "composite_provider_risk",
                "metric_value": row.efficiency_score,
                "severity": row.financial_risk,
                "rationale": (
                    f"Denial rate {row.denial_rate:.1%}, benchmark variance "
                    f"{row.benchmark_variance_pct:.1%}, PMPM contribution ${row.pmpm_contribution:,.2f}."
                ),
            }
        )

    monthly = monthly_trends.copy()
    for metric in ["total_paid", "pmpm", "denial_rate"]:
        monthly[f"{metric}_zscore"] = _zscore(monthly[metric])
        month_flags = monthly[monthly[f"{metric}_zscore"].abs() > 2]
        for row in month_flags.itertuples(index=False):
            records.append(
                {
                    "anomaly_type": "Monthly trend break",
                    "entity_type": "month",
                    "entity_id": str(row.service_month.date()),
                    "service_month": row.service_month,
                    "metric": metric,
                    "metric_value": getattr(row, metric),
                    "severity": "High" if abs(getattr(row, f"{metric}_zscore")) > 2.5 else "Medium",
                    "rationale": f"{metric} z-score {getattr(row, f'{metric}_zscore'):.2f}.",
                }
            )

    anomalies = pd.DataFrame(records)
    if anomalies.empty:
        return pd.DataFrame(
            columns=["anomaly_type", "entity_type", "entity_id", "service_month", "metric", "metric_value", "severity", "rationale"]
        )
    severity_order = pd.CategoricalDtype(["High", "Medium", "Low"], ordered=True)
    anomalies["severity"] = anomalies["severity"].astype(severity_order)
    return anomalies.sort_values(["severity", "anomaly_type"]).reset_index(drop=True)
