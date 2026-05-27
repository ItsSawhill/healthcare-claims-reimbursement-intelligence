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

tab_overview, tab_provider, tab_reimbursement, tab_utilization, tab_anomalies, tab_forecast, tab_report = st.tabs(
    ["Overview", "Provider Risk", "Reimbursement", "Utilization", "Anomalies", "Forecasts", "Executive Report"]
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
