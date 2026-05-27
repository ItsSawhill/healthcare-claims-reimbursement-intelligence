from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TABLE_DIR = ROOT / "outputs" / "tables"
REPORT_DIR = ROOT / "outputs" / "reports"
FIGURE_DIR = ROOT / "outputs" / "figures"

from cms_benchmark_loader import apply_cms_or_fallback_benchmarks


def test_required_output_files_exist():
    required_files = [
        TABLE_DIR / "provider_kpis.csv",
        TABLE_DIR / "monthly_trends.csv",
        TABLE_DIR / "reimbursement_benchmarking.csv",
        TABLE_DIR / "utilization_summary.csv",
        TABLE_DIR / "anomalies.csv",
        TABLE_DIR / "forecast_summary.csv",
        TABLE_DIR / "cost_driver_analysis.csv",
        TABLE_DIR / "scenario_rate_change.csv",
        TABLE_DIR / "scenario_utilization_change.csv",
        TABLE_DIR / "scenario_provider_contract_change.csv",
        TABLE_DIR / "scenario_benchmark_alignment.csv",
        TABLE_DIR / "scenario_summary.csv",
        REPORT_DIR / "executive_summary.md",
        REPORT_DIR / "executive_workbook.xlsx",
        FIGURE_DIR / "pmpm_trend.png",
        FIGURE_DIR / "provider_efficiency_ranking.png",
        FIGURE_DIR / "utilization_trend_dashboard.png",
        FIGURE_DIR / "scenario_financial_impact.png",
        FIGURE_DIR / "scenario_pmpm_impact.png",
        FIGURE_DIR / "provider_scenario_exposure.png",
        FIGURE_DIR / "benchmark_alignment_impact.png",
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
        "Scenario Summary",
        "Rate Change Impact",
        "Utilization Impact",
        "Provider Contract Impact",
        "Benchmark Alignment Impact",
    }
    assert expected_sheets.issubset(set(workbook.sheetnames))


def test_scenario_tables_have_required_columns_and_math():
    required_columns = {
        "scenario_name",
        "baseline_paid_amount",
        "simulated_paid_amount",
        "dollar_impact",
        "percent_impact",
        "pmpm_impact",
        "benchmark_variance_impact",
    }
    for filename in [
        "scenario_rate_change.csv",
        "scenario_utilization_change.csv",
        "scenario_provider_contract_change.csv",
        "scenario_benchmark_alignment.csv",
    ]:
        scenario = pd.read_csv(TABLE_DIR / filename)
        assert required_columns.issubset(scenario.columns)
        diff = scenario["simulated_paid_amount"] - scenario["baseline_paid_amount"]
        assert np.allclose(diff, scenario["dollar_impact"], atol=0.01, equal_nan=True)

    summary = pd.read_csv(TABLE_DIR / "scenario_summary.csv")
    assert required_columns.issubset(summary.columns)
    diff = summary["simulated_paid_amount"] - summary["baseline_paid_amount"]
    assert np.allclose(diff, summary["dollar_impact"], atol=0.01, equal_nan=True)


def test_cms_benchmark_loader_fallback_uses_synthetic_source(tmp_path):
    claims = pd.DataFrame(
        {
            "procedure_code": ["99213", "93000"],
            "medicare_benchmark_amount": [100.0, 25.0],
        }
    )
    enriched, source = apply_cms_or_fallback_benchmarks(claims, tmp_path / "missing_cms.csv")
    assert source == "synthetic_medicare_style"
    assert set(enriched["benchmark_source"]) == {"synthetic_medicare_style"}
    assert enriched["medicare_benchmark_amount"].tolist() == [100.0, 25.0]


def test_pipeline_runs_end_to_end():
    result = subprocess.run(
        [sys.executable, "src/run_pipeline.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "pipeline completed" in result.stdout
