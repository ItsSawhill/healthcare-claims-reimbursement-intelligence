import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def _minmax(series: pd.Series) -> pd.Series:
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series(0.0, index=series.index)
    return (series - minimum) / (maximum - minimum)


def add_reimbursement_severity(provider_kpis: pd.DataFrame) -> pd.DataFrame:
    provider = provider_kpis.copy()
    variance_abs = provider["benchmark_variance_pct"].abs().fillna(0)
    provider["reimbursement_deviation_score"] = (variance_abs * 100).clip(0, 100)
    provider["reimbursement_deviation_severity"] = np.select(
        [
            variance_abs >= 0.35,
            variance_abs >= 0.20,
            variance_abs >= 0.10,
        ],
        ["Critical", "High", "Moderate"],
        default="Normal",
    )
    return provider


def segment_providers(provider_kpis: pd.DataFrame, n_clusters: int = 4, seed: int = 42) -> pd.DataFrame:
    provider = add_reimbursement_severity(provider_kpis)
    features = [
        "total_paid",
        "average_cost_per_claim",
        "reimbursement_rate",
        "denial_rate",
        "pmpm_contribution",
        "benchmark_variance_pct",
        "efficiency_score",
    ]
    model_frame = provider[features].replace([np.inf, -np.inf], np.nan).fillna(0)
    scaled = StandardScaler().fit_transform(model_frame)
    clusters = KMeans(n_clusters=min(n_clusters, len(provider)), random_state=seed, n_init=10).fit_predict(scaled)
    provider["provider_cluster"] = clusters

    cluster_summary = provider.groupby("provider_cluster").agg(
        avg_paid=("total_paid", "mean"),
        avg_denial=("denial_rate", "mean"),
        avg_efficiency=("efficiency_score", "mean"),
        avg_benchmark_variance=("benchmark_variance_pct", "mean"),
    )
    cost_cluster = cluster_summary["avg_paid"].idxmax()
    denial_cluster = cluster_summary["avg_denial"].idxmax()
    efficient_cluster = cluster_summary["avg_efficiency"].idxmin()
    benchmark_cluster = cluster_summary["avg_benchmark_variance"].abs().idxmax()

    labels = {}
    for cluster_id in cluster_summary.index:
        if cluster_id == cost_cluster:
            labels[cluster_id] = "High-cost provider segment"
        elif cluster_id == denial_cluster:
            labels[cluster_id] = "Denial-risk provider segment"
        elif cluster_id == efficient_cluster:
            labels[cluster_id] = "Efficient provider segment"
        elif cluster_id == benchmark_cluster:
            labels[cluster_id] = "Benchmark-variance segment"
        else:
            labels[cluster_id] = "Moderate-risk provider segment"
    provider["provider_segment"] = provider["provider_cluster"].map(labels)

    provider["provider_risk_score"] = (
        _minmax(provider["average_cost_per_claim"]) * 25
        + _minmax(provider["denial_rate"]) * 25
        + _minmax(provider["pmpm_contribution"]) * 20
        + _minmax(provider["benchmark_variance_pct"].abs()) * 20
        + _minmax(provider["total_paid"]) * 10
    ).round(2)
    provider["provider_risk_tier"] = np.select(
        [
            provider["provider_risk_score"] >= 70,
            provider["provider_risk_score"] >= 45,
            provider["provider_risk_score"] >= 25,
        ],
        ["Critical", "High", "Moderate"],
        default="Low",
    )
    provider["high_cost_provider_flag"] = (
        provider["total_paid"] >= provider["total_paid"].quantile(0.90)
    ).astype(int)
    return provider.sort_values(["provider_risk_score", "total_paid"], ascending=False)


def cost_driver_analysis(claims: pd.DataFrame) -> pd.DataFrame:
    total_paid = claims["paid_amount"].sum()
    drivers = claims.groupby(["service_category", "provider_id", "provider_name", "payer"]).agg(
        total_claims=("claim_id", "count"),
        total_paid=("paid_amount", "sum"),
        total_allowed=("allowed_amount", "sum"),
        denial_rate=("denial_flag", "mean"),
        avg_paid_per_claim=("paid_amount", "mean"),
        benchmark_total=("medicare_benchmark_amount", "sum"),
    )
    drivers["paid_share"] = drivers["total_paid"] / total_paid if total_paid else 0
    drivers["benchmark_variance_amount"] = drivers["total_allowed"] - drivers["benchmark_total"]
    drivers["benchmark_variance_pct"] = drivers["benchmark_variance_amount"] / drivers["benchmark_total"].replace(0, pd.NA)
    return drivers.reset_index().sort_values("total_paid", ascending=False)
