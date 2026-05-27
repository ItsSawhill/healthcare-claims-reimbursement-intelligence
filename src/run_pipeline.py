from pathlib import Path

from advanced_analytics import cost_driver_analysis, segment_providers
from anomaly_detection import detect_anomalies
from claims_analytics import claims_summary, monthly_trends
from forecasting import forecast_monthly_metrics, save_forecast_plots
from ingest import load_or_create_claims
from preprocess import clean_claims
from provider_kpis import build_provider_kpis
from reimbursement import reimbursement_benchmarking
from reporting import save_core_plots, write_executive_summary
from utilization import high_utilization_segments, utilization_summary


BASE_DIR = Path(__file__).resolve().parents[1]
TABLE_DIR = BASE_DIR / "outputs" / "tables"
FIGURE_DIR = BASE_DIR / "outputs" / "figures"
REPORT_DIR = BASE_DIR / "outputs" / "reports"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def write_table(df, filename: str) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLE_DIR / filename, index=False)


def main() -> None:
    for directory in [TABLE_DIR, FIGURE_DIR, REPORT_DIR, PROCESSED_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    raw_claims = load_or_create_claims(BASE_DIR / "data" / "raw" / "claims.csv", n_rows=20000)
    claims = clean_claims(raw_claims)
    claims.to_csv(PROCESSED_DIR / "claims_clean.csv", index=False)

    monthly = monthly_trends(claims)
    reimbursement = reimbursement_benchmarking(claims)
    provider = build_provider_kpis(claims, reimbursement)
    provider = segment_providers(provider)
    utilization = utilization_summary(claims)
    high_util = high_utilization_segments(claims)
    cost_drivers = cost_driver_analysis(claims)
    anomalies = detect_anomalies(claims, provider, monthly)
    forecast = forecast_monthly_metrics(monthly, horizon=3)

    write_table(monthly, "monthly_trends.csv")
    write_table(reimbursement, "reimbursement_benchmarking.csv")
    write_table(provider, "provider_kpis.csv")
    write_table(cost_drivers, "cost_driver_analysis.csv")
    write_table(utilization, "utilization_summary.csv")
    write_table(high_util, "high_utilization_segments.csv")
    write_table(anomalies, "anomalies.csv")
    write_table(forecast, "forecast_summary.csv")

    for dims, filename in [
        (["service_month"], "claims_summary_by_month.csv"),
        (["provider_id", "provider_name"], "claims_summary_by_provider.csv"),
        (["procedure_code"], "claims_summary_by_procedure.csv"),
        (["diagnosis_code"], "claims_summary_by_diagnosis.csv"),
        (["region"], "claims_summary_by_region.csv"),
        (["payer"], "claims_summary_by_payer.csv"),
        (["service_category"], "claims_summary_by_service_category.csv"),
    ]:
        write_table(claims_summary(claims, dims), filename)

    save_core_plots(monthly, provider, reimbursement, anomalies, utilization, FIGURE_DIR)
    save_forecast_plots(monthly, forecast, FIGURE_DIR)
    write_executive_summary(
        monthly,
        provider,
        reimbursement,
        anomalies,
        forecast,
        utilization,
        cost_drivers,
        REPORT_DIR / "executive_summary.md",
    )

    print("Healthcare claims reimbursement intelligence pipeline completed.")
    print(f"Rows processed: {len(claims):,}")
    print(f"Tables written: {TABLE_DIR}")
    print(f"Figures written: {FIGURE_DIR}")
    print(f"Executive report: {REPORT_DIR / 'executive_summary.md'}")


if __name__ == "__main__":
    main()
