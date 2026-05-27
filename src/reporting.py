from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")
import matplotlib.pyplot as plt
import pandas as pd


def _format_axes(ax) -> None:
    ax.grid(alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_core_plots(
    monthly: pd.DataFrame,
    provider_kpis: pd.DataFrame,
    reimbursement: pd.DataFrame,
    anomalies: pd.DataFrame,
    utilization: pd.DataFrame,
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.plot(monthly["service_month"], monthly["total_paid"], marker="o", linewidth=2.2, label="Paid amount")
    ax.plot(monthly["service_month"], monthly["total_allowed"], marker="o", linewidth=2.2, label="Allowed amount")
    ax.set_title("Claims Cost Trend", fontsize=14, weight="bold")
    ax.set_xlabel("Service Month")
    ax.set_ylabel("Amount")
    _format_axes(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figure_dir / "monthly_cost_trend.png", dpi=180)
    plt.close()

    top = provider_kpis.nlargest(10, "total_paid").sort_values("total_paid")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(top["provider_name"], top["total_paid"], color="#2f6f8f")
    ax.set_title("Top Providers by Paid Amount", fontsize=14, weight="bold")
    ax.set_xlabel("Total Paid")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "top_provider_costs.png", dpi=180)
    plt.close()

    bench = reimbursement.groupby("service_category")["benchmark_variance_pct"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(9, 5))
    bench.plot(kind="bar", ax=ax, color="#6d8f3f")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Average Benchmark Variance by Service Category", fontsize=14, weight="bold")
    ax.set_ylabel("Allowed vs Medicare Benchmark")
    ax.set_xlabel("")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "benchmark_variance_by_service.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(monthly["service_month"], monthly["pmpm"], marker="o", linewidth=2.4, color="#1f7a5c")
    ax.set_title("PMPM Trend Over Time", fontsize=14, weight="bold")
    ax.set_xlabel("Service Month")
    ax.set_ylabel("Paid Amount Per Member Month")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "pmpm_trend.png", dpi=180)
    plt.close()

    provider_variance = provider_kpis.nlargest(12, "benchmark_variance_pct").sort_values("benchmark_variance_pct")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(provider_variance["provider_name"], provider_variance["benchmark_variance_pct"], color="#9b5f31")
    ax.axvline(0.20, color="#8b1e3f", linestyle="--", linewidth=1.2, label="20% review threshold")
    ax.set_title("Reimbursement Variance by Provider", fontsize=14, weight="bold")
    ax.set_xlabel("Allowed vs Medicare-Style Benchmark")
    _format_axes(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figure_dir / "reimbursement_variance_by_provider.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(provider_kpis["denial_rate"], bins=14, color="#5b7c99", edgecolor="white")
    ax.set_title("Denial Rate Distribution", fontsize=14, weight="bold")
    ax.set_xlabel("Provider Denial Rate")
    ax.set_ylabel("Provider Count")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "denial_rate_distribution.png", dpi=180)
    plt.close()

    ranked = provider_kpis.nlargest(12, "provider_risk_score").sort_values("provider_risk_score")
    colors = ranked["provider_risk_tier"].map({"Critical": "#8b1e3f", "High": "#c45f35", "Moderate": "#d6a23f", "Low": "#4f8f6f"})
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(ranked["provider_name"], ranked["provider_risk_score"], color=colors)
    ax.set_title("Provider Efficiency and Risk Ranking", fontsize=14, weight="bold")
    ax.set_xlabel("Provider Risk Score")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "provider_efficiency_ranking.png", dpi=180)
    plt.close()

    if not anomalies.empty:
        anomaly_months = anomalies.dropna(subset=["service_month"]).copy()
        anomaly_months["service_month"] = pd.to_datetime(anomaly_months["service_month"]).dt.to_period("M").dt.to_timestamp()
        freq = anomaly_months.groupby("service_month").size()
    else:
        freq = pd.Series(dtype=int)
    fig, ax = plt.subplots(figsize=(10, 5))
    if not freq.empty:
        ax.bar(freq.index, freq.values, width=20, color="#744c7d")
    ax.set_title("Anomaly Frequency by Month", fontsize=14, weight="bold")
    ax.set_xlabel("Service Month")
    ax.set_ylabel("Anomaly Count")
    _format_axes(ax)
    fig.tight_layout()
    fig.savefig(figure_dir / "anomaly_frequency_by_month.png", dpi=180)
    plt.close()

    util = utilization.groupby("service_month").agg(
        visits_per_1000_members=("visits_per_1000_members", "sum"),
        cost_per_visit=("cost_per_visit", "mean"),
        pmpm=("pmpm", "sum"),
    ).reset_index()
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    axes[0].plot(util["service_month"], util["visits_per_1000_members"], color="#2f6f8f", marker="o")
    axes[0].set_ylabel("Visits / 1,000")
    axes[1].plot(util["service_month"], util["cost_per_visit"], color="#9b5f31", marker="o")
    axes[1].set_ylabel("Cost / Visit")
    axes[2].plot(util["service_month"], util["pmpm"], color="#1f7a5c", marker="o")
    axes[2].set_ylabel("PMPM")
    axes[2].set_xlabel("Service Month")
    for axis in axes:
        _format_axes(axis)
    fig.suptitle("Utilization Trend Dashboard", fontsize=14, weight="bold")
    fig.tight_layout()
    fig.savefig(figure_dir / "utilization_trend_dashboard.png", dpi=180)
    plt.close()


def write_executive_summary(
    monthly: pd.DataFrame,
    provider_kpis: pd.DataFrame,
    reimbursement: pd.DataFrame,
    anomalies: pd.DataFrame,
    forecast: pd.DataFrame,
    utilization: pd.DataFrame,
    cost_drivers: pd.DataFrame,
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    latest = monthly.sort_values("service_month").iloc[-1]
    prior = monthly.sort_values("service_month").iloc[-2]
    paid_change = (latest.total_paid - prior.total_paid) / prior.total_paid
    next_paid = forecast[(forecast["metric"] == "total_paid")].sort_values("forecast_month").iloc[0]
    next_pmpm = forecast[(forecast["metric"] == "pmpm")].sort_values("forecast_month").iloc[0]
    top_provider = provider_kpis.sort_values("total_paid", ascending=False).iloc[0]
    highest_risk = provider_kpis.sort_values("provider_risk_score", ascending=False).iloc[0]
    top_driver = cost_drivers.iloc[0]
    above_benchmark = reimbursement[reimbursement["benchmark_flag"] == "Above benchmark"]
    high_anomalies = anomalies[anomalies["severity"].astype(str) == "High"] if not anomalies.empty else pd.DataFrame()
    top_anomaly_lines = []
    for row in anomalies.head(5).itertuples(index=False):
        top_anomaly_lines.append(f"- {row.anomaly_type}: {row.entity_id} | {row.metric} = {row.metric_value:,.2f} | {row.rationale}")
    top_anomalies = "\n".join(top_anomaly_lines) if top_anomaly_lines else "- No anomaly candidates exceeded configured thresholds."
    util_latest = utilization.groupby("service_month").agg(
        visits_per_1000_members=("visits_per_1000_members", "sum"),
        cost_per_visit=("cost_per_visit", "mean"),
        pmpm=("pmpm", "sum"),
    ).reset_index().sort_values("service_month").iloc[-1]

    text = f"""# Executive Summary

## Key Findings
- Latest service month: {latest.service_month:%B %Y}
- Total paid amount: ${latest.total_paid:,.0f}, a {paid_change:.1%} change from the prior month.
- PMPM: ${latest.pmpm:,.2f}; denial rate: {latest.denial_rate:.1%}; total claims: {latest.total_claims:,.0f}.
- Next-month paid amount forecast ({next_paid.forecast_month:%B %Y}): ${next_paid.forecast_value:,.0f}.
- Next-month PMPM forecast ({next_pmpm.forecast_month:%B %Y}): ${next_pmpm.forecast_value:,.2f}.

## Financial Insights
- Largest paid provider: {top_provider.provider_name} ({top_provider.provider_id}) with ${top_provider.total_paid:,.0f} in paid claims.
- Largest cost-driver segment: {top_driver.service_category} / {top_driver.provider_name} / {top_driver.payer}, representing {top_driver.paid_share:.1%} of total paid amount.
- Providers or service lines above benchmark: {len(above_benchmark):,} provider-service-payer combinations.

## Provider Risk
- Highest provider risk score: {highest_risk.provider_name} ({highest_risk.provider_id}) at {highest_risk.provider_risk_score:.1f}, tiered as {highest_risk.provider_risk_tier}.
- Risk detail: denial rate {highest_risk.denial_rate:.1%}, benchmark variance {highest_risk.benchmark_variance_pct:.1%}, PMPM contribution ${highest_risk.pmpm_contribution:,.2f}.
- Provider segment: {highest_risk.provider_segment}.

## Utilization Trends
- Latest visits per 1,000 members: {util_latest.visits_per_1000_members:,.1f}.
- Latest average cost per visit: ${util_latest.cost_per_visit:,.2f}.
- Latest utilization-derived PMPM: ${util_latest.pmpm:,.2f}.

## Anomaly Review
- High-severity anomaly records: {len(high_anomalies):,}.
- Primary anomaly themes include high billed claims, provider benchmark variance, denial outliers, and monthly PMPM or paid amount breaks.

### Top Anomaly Candidates
{top_anomalies}

## Forecast Commentary
- The next-month paid forecast is ${next_paid.forecast_value:,.0f}, based on a blend of rolling average, exponential smoothing, and recent trend.
- The next-month PMPM forecast is ${next_pmpm.forecast_value:,.2f}; leadership should compare this value with budget and medical cost targets.

## Recommended Actions
1. Review high-benchmark providers for contract terms, coding mix, and medical necessity documentation.
2. Audit providers with elevated denial rates to identify authorization, eligibility, and coding defects.
3. Monitor next-month PMPM and paid forecast against budget; create an escalation threshold for variance above 5%.
4. Prioritize service categories with persistent above-benchmark reimbursement for renegotiation or utilization management.
5. Use provider segments to tailor interventions: contract review for high-cost providers, denial workflow review for denial-risk providers, and utilization management for high-PMPM service lines.
6. Refresh this pipeline monthly and publish the CSV outputs to the executive dashboard layer.
"""
    report_path.write_text(text)


def write_excel_workbook(
    monthly: pd.DataFrame,
    provider_kpis: pd.DataFrame,
    reimbursement: pd.DataFrame,
    utilization: pd.DataFrame,
    anomalies: pd.DataFrame,
    forecast: pd.DataFrame,
    workbook_path: Path,
) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    latest = monthly.sort_values("service_month").iloc[-1]
    next_paid = forecast[forecast["metric"] == "total_paid"].sort_values("forecast_month").iloc[0]
    next_pmpm = forecast[forecast["metric"] == "pmpm"].sort_values("forecast_month").iloc[0]
    highest_risk = provider_kpis.sort_values("provider_risk_score", ascending=False).iloc[0]

    executive = pd.DataFrame(
        [
            {"Metric": "Latest service month", "Value": latest.service_month.strftime("%Y-%m")},
            {"Metric": "Total paid amount", "Value": latest.total_paid},
            {"Metric": "PMPM", "Value": latest.pmpm},
            {"Metric": "Denial rate", "Value": latest.denial_rate},
            {"Metric": "Total claims", "Value": latest.total_claims},
            {"Metric": "Next-month paid forecast", "Value": next_paid.forecast_value},
            {"Metric": "Next-month PMPM forecast", "Value": next_pmpm.forecast_value},
            {"Metric": "Highest-risk provider", "Value": f"{highest_risk.provider_name} ({highest_risk.provider_id})"},
            {"Metric": "Highest provider risk score", "Value": highest_risk.provider_risk_score},
        ]
    )

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        executive.to_excel(writer, sheet_name="Executive Summary", index=False)
        provider_kpis.to_excel(writer, sheet_name="Provider KPIs", index=False)
        monthly.to_excel(writer, sheet_name="Monthly Trends", index=False)
        reimbursement.to_excel(writer, sheet_name="Reimbursement Benchmarking", index=False)
        utilization.to_excel(writer, sheet_name="Utilization Summary", index=False)
        anomalies.to_excel(writer, sheet_name="Anomalies", index=False)
        forecast.to_excel(writer, sheet_name="Forecasts", index=False)

        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.style = "Headline 3"
            for column_cells in sheet.columns:
                max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 36)
