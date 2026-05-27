from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
TABLE_DIR = BASE_DIR / "outputs" / "tables"
REPORT_PATH = BASE_DIR / "outputs" / "reports" / "executive_summary.md"


@st.cache_data
def load_table(filename: str) -> pd.DataFrame:
    path = TABLE_DIR / filename
    if not path.exists():
        st.error(f"Missing required output table: {path}")
        st.stop()
    return pd.read_csv(path)


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


st.set_page_config(
    page_title="Healthcare Claims & Reimbursement Intelligence",
    layout="wide",
)

monthly = load_table("monthly_trends.csv")
provider = load_table("provider_kpis.csv")
reimbursement = load_table("reimbursement_benchmarking.csv")
utilization = load_table("utilization_summary.csv")
anomalies = load_table("anomalies.csv")
forecast = load_table("forecast_summary.csv")
cost_drivers = load_table("cost_driver_analysis.csv")
scenario_summary = load_table("scenario_summary.csv")
scenario_rate = load_table("scenario_rate_change.csv")
scenario_utilization = load_table("scenario_utilization_change.csv")
scenario_contract = load_table("scenario_provider_contract_change.csv")
scenario_benchmark = load_table("scenario_benchmark_alignment.csv")

monthly["service_month"] = pd.to_datetime(monthly["service_month"])
utilization["service_month"] = pd.to_datetime(utilization["service_month"])
if "service_month" in anomalies.columns:
    anomalies["service_month"] = pd.to_datetime(anomalies["service_month"], errors="coerce")

st.title("Healthcare Claims & Reimbursement Intelligence")
st.caption("Executive analytics for claims cost, utilization, reimbursement benchmarking, provider risk, anomalies, and forecasting.")

with st.sidebar:
    st.header("Filters")
    selected_region = st.multiselect("Region", sorted(provider["region"].dropna().unique()))
    selected_risk = st.multiselect("Provider Risk Tier", sorted(provider["provider_risk_tier"].dropna().unique()))
    selected_service = st.multiselect("Service Category", sorted(reimbursement["service_category"].dropna().unique()))

provider_view = provider.copy()
if selected_region:
    provider_view = provider_view[provider_view["region"].isin(selected_region)]
if selected_risk:
    provider_view = provider_view[provider_view["provider_risk_tier"].isin(selected_risk)]

reimbursement_view = reimbursement.copy()
utilization_view = utilization.copy()
if selected_service:
    reimbursement_view = reimbursement_view[reimbursement_view["service_category"].isin(selected_service)]
    utilization_view = utilization_view[utilization_view["service_category"].isin(selected_service)]

latest = monthly.sort_values("service_month").iloc[-1]
next_paid = forecast[forecast["metric"] == "total_paid"].sort_values("forecast_month").iloc[0]
next_pmpm = forecast[forecast["metric"] == "pmpm"].sort_values("forecast_month").iloc[0]

kpi_cols = st.columns(5)
kpi_cols[0].metric("Latest Paid Amount", money(latest["total_paid"]))
kpi_cols[1].metric("Latest PMPM", f"${latest['pmpm']:,.2f}")
kpi_cols[2].metric("Denial Rate", pct(latest["denial_rate"]))
kpi_cols[3].metric("High-Risk Providers", f"{(provider['provider_risk_tier'].isin(['Critical', 'High'])).sum():,}")
kpi_cols[4].metric("Next Paid Forecast", money(next_paid["forecast_value"]))

tab_overview, tab_provider, tab_reimbursement, tab_utilization, tab_scenario, tab_anomalies, tab_forecast, tab_report = st.tabs(
    [
        "Overview",
        "Provider Risk",
        "Reimbursement",
        "Utilization",
        "Scenario Simulation",
        "Anomalies",
        "Forecasts",
        "Executive Report",
    ]
)

with tab_overview:
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("Monthly Paid Amount and PMPM")
        chart_data = monthly.set_index("service_month")[["total_paid", "pmpm"]]
        st.line_chart(chart_data)
    with right:
        st.subheader("Top Cost Drivers")
        st.dataframe(
            cost_drivers[
                ["service_category", "provider_name", "payer", "total_paid", "paid_share", "benchmark_variance_pct"]
            ].head(10),
            use_container_width=True,
            hide_index=True,
        )

with tab_provider:
    st.subheader("Provider KPI and Risk Ranking")
    st.dataframe(
        provider_view[
            [
                "provider_id",
                "provider_name",
                "region",
                "total_claims",
                "total_paid",
                "denial_rate",
                "pmpm_contribution",
                "benchmark_variance_pct",
                "provider_risk_score",
                "provider_risk_tier",
                "provider_segment",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(provider_view.nlargest(15, "provider_risk_score").set_index("provider_name")["provider_risk_score"])

with tab_reimbursement:
    st.subheader("Medicare-Style Benchmarking")
    st.dataframe(
        reimbursement_view[
            [
                "provider_name",
                "service_category",
                "payer",
                "total_claims",
                "paid_to_billed_rate",
                "allowed_to_billed_rate",
                "benchmark_variance_pct",
                "benchmark_flag",
            ]
        ].sort_values("benchmark_variance_pct", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

with tab_utilization:
    st.subheader("Utilization Trend")
    util_month = utilization_view.groupby("service_month").agg(
        visits_per_1000_members=("visits_per_1000_members", "sum"),
        cost_per_visit=("cost_per_visit", "mean"),
        pmpm=("pmpm", "sum"),
    )
    st.line_chart(util_month)
    st.dataframe(utilization_view, use_container_width=True, hide_index=True)

with tab_scenario:
    st.subheader("Reimbursement Scenario Simulation")
    st.caption("Precomputed scenario outputs are generated by the pipeline. The sliders below provide lightweight live sensitivity estimates.")
    scenario_cols = st.columns(3)
    rate_change = scenario_cols[0].slider("Reimbursement rate change", -15, 15, 5, format="%d%%") / 100
    utilization_change = scenario_cols[1].slider("Utilization change", -15, 20, 10, format="%d%%") / 100
    provider_choice = scenario_cols[2].selectbox(
        "Provider exposure focus",
        ["All providers"] + sorted(provider["provider_name"].dropna().unique().tolist()),
    )

    scenario_base = provider.copy()
    if provider_choice != "All providers":
        scenario_base = scenario_base[scenario_base["provider_name"] == provider_choice]
    baseline_paid = scenario_base["total_paid"].sum()
    member_months = monthly["member_months"].max()
    live_rate_impact = baseline_paid * rate_change
    live_util_impact = baseline_paid * utilization_change

    live_cols = st.columns(4)
    live_cols[0].metric("Selected Baseline Paid", money(baseline_paid))
    live_cols[1].metric("Rate Change Impact", money(live_rate_impact))
    live_cols[2].metric("Utilization Impact", money(live_util_impact))
    live_cols[3].metric("Combined PMPM Impact", f"${(live_rate_impact + live_util_impact) / member_months:,.2f}")

    st.subheader("Precomputed Scenario Summary")
    st.dataframe(scenario_summary, use_container_width=True, hide_index=True)
    st.bar_chart(scenario_summary.set_index("scenario_name")["dollar_impact"])

    st.subheader("Top Affected Providers")
    scenario_table = pd.concat(
        [
            scenario_rate.assign(source_scenario="Rate Change +5%"),
            scenario_utilization.assign(source_scenario="Utilization +10%"),
            scenario_contract.assign(source_scenario="Top Provider Contract -5%"),
            scenario_benchmark.assign(source_scenario="Benchmark Alignment"),
        ],
        ignore_index=True,
    )
    top_exposure = scenario_table.sort_values("dollar_impact", key=lambda s: s.abs(), ascending=False).head(15)
    st.dataframe(
        top_exposure[
            [
                "source_scenario",
                "provider_id",
                "provider_name",
                "service_category",
                "baseline_paid_amount",
                "simulated_paid_amount",
                "dollar_impact",
                "pmpm_impact",
                "benchmark_variance_impact",
                "risk_rank",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

with tab_anomalies:
    st.subheader("Anomaly Review Queue")
    severity = st.multiselect("Severity", sorted(anomalies["severity"].dropna().unique()))
    anomaly_view = anomalies[anomalies["severity"].isin(severity)] if severity else anomalies
    st.dataframe(anomaly_view, use_container_width=True, hide_index=True)

with tab_forecast:
    st.subheader("Forecast Summary")
    st.metric("Next PMPM Forecast", f"${next_pmpm['forecast_value']:,.2f}")
    forecast_chart = forecast.pivot(index="forecast_month", columns="metric", values="forecast_value")
    st.line_chart(forecast_chart)
    st.dataframe(forecast, use_container_width=True, hide_index=True)

with tab_report:
    st.subheader("Executive Summary")
    if REPORT_PATH.exists():
        st.markdown(REPORT_PATH.read_text())
    else:
        st.warning("Run `python src/run_pipeline.py` to generate the executive summary.")
