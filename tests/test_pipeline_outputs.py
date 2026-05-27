from pathlib import Path

import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"
FIGURE_DIR = ROOT / "outputs" / "figures"


def test_required_output_files_exist():
    required_files = [
        TABLE_DIR / "provider_kpis.csv",
        TABLE_DIR / "monthly_trends.csv",
        TABLE_DIR / "reimbursement_benchmarking.csv",
        TABLE_DIR / "utilization_summary.csv",
        TABLE_DIR / "anomalies.csv",
        TABLE_DIR / "forecast_summary.csv",
        TABLE_DIR / "cost_driver_analysis.csv",
        REPORT_DIR / "executive_summary.md",
        REPORT_DIR / "executive_workbook.xlsx",
        FIGURE_DIR / "pmpm_trend.png",
        FIGURE_DIR / "provider_efficiency_ranking.png",
        FIGURE_DIR / "utilization_trend_dashboard.png",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    assert not missing, f"Missing expected outputs: {missing}"


def test_provider_kpi_required_columns():
    provider = pd.read_csv(TABLE_DIR / "provider_kpis.csv")
    required_columns = {
        "provider_id",
        "provider_name",
        "total_claims",
        "total_paid",
        "denial_rate",
        "pmpm_contribution",
        "benchmark_variance_pct",
        "provider_risk_score",
        "provider_risk_tier",
        "provider_segment",
        "high_cost_provider_flag",
    }
    assert required_columns.issubset(provider.columns)
    assert len(provider) > 0
    assert provider["provider_risk_score"].between(0, 100).all()


def test_monthly_trends_required_columns():
    monthly = pd.read_csv(TABLE_DIR / "monthly_trends.csv")
    required_columns = {
        "service_month",
        "total_claims",
        "total_paid",
        "denial_rate",
        "pmpm",
        "claims_per_1000_members",
    }
    assert required_columns.issubset(monthly.columns)
    assert len(monthly) >= 12
    assert (monthly["total_claims"] > 0).all()


def test_reimbursement_and_utilization_outputs_have_required_columns():
    reimbursement = pd.read_csv(TABLE_DIR / "reimbursement_benchmarking.csv")
    utilization = pd.read_csv(TABLE_DIR / "utilization_summary.csv")
    assert {
        "provider_id",
        "service_category",
        "paid_to_billed_rate",
        "allowed_to_billed_rate",
        "benchmark_variance_pct",
        "benchmark_flag",
    }.issubset(reimbursement.columns)
    assert {
        "service_month",
        "service_category",
        "visits_per_1000_members",
        "cost_per_visit",
        "pmpm",
    }.issubset(utilization.columns)


def test_forecast_and_anomaly_outputs_have_required_columns():
    forecast = pd.read_csv(TABLE_DIR / "forecast_summary.csv")
    anomalies = pd.read_csv(TABLE_DIR / "anomalies.csv")
    assert {"forecast_month", "metric", "forecast_value", "method"}.issubset(forecast.columns)
    assert set(forecast["metric"]) == {"total_paid", "total_claims", "pmpm"}
    assert {"anomaly_type", "entity_type", "metric", "metric_value", "severity", "rationale"}.issubset(anomalies.columns)


def test_excel_workbook_sheets():
    workbook = load_workbook(REPORT_DIR / "executive_workbook.xlsx", read_only=True)
    expected_sheets = {
        "Executive Summary",
        "Provider KPIs",
        "Monthly Trends",
        "Reimbursement Benchmarking",
        "Utilization Summary",
        "Anomalies",
        "Forecasts",
    }
    assert expected_sheets.issubset(set(workbook.sheetnames))
