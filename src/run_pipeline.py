from pathlib import Path

from advanced_analytics import cost_driver_analysis, segment_providers
from anomaly_detection import detect_anomalies
from claims_analytics import claims_summary, monthly_trends
from cms_benchmark_loader import apply_cms_or_fallback_benchmarks
from cms_provider_data_loader import (
    create_cms_provider_service_benchmarks,
    enrich_claims_with_cms_provider_benchmarks,
    load_cms_provider_service_data,
)
from forecasting import forecast_monthly_metrics, save_forecast_plots
from ingest import load_or_create_claims
from preprocess import clean_claims
from provider_kpis import build_provider_kpis
from reimbursement import reimbursement_benchmarking
from reporting import save_core_plots, write_excel_workbook, write_executive_summary
from scenario_simulation import (
    generate_scenario_summary,
    save_scenario_plots,
    simulate_benchmark_alignment,
    simulate_provider_contract_change,
    simulate_reimbursement_rate_change,
    simulate_utilization_change,
)
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
    claims, benchmark_source = apply_cms_or_fallback_benchmarks(claims, BASE_DIR / "data" / "raw" / "cms_benchmarks.csv")
    cms_provider_service = load_cms_provider_service_data(BASE_DIR / "data" / "raw" / "cms_provider_service.csv")
    cms_provider_benchmarks = create_cms_provider_service_benchmarks(cms_provider_service)
    claims, cms_provider_source = enrich_claims_with_cms_provider_benchmarks(claims, cms_provider_benchmarks)
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
    rate_provider, rate_service = simulate_reimbursement_rate_change(claims, rate_change=0.05)
    util_provider, util_service = simulate_utilization_change(claims, utilization_change=0.10)
    contract_provider, contract_service = simulate_provider_contract_change(claims, contract_change=-0.05)
    benchmark_provider, benchmark_service = simulate_benchmark_alignment(claims, alignment_rate=1.0)
    scenario_summary = generate_scenario_summary(rate_provider, util_provider, contract_provider, benchmark_provider)

    write_table(monthly, "monthly_trends.csv")
    write_table(reimbursement, "reimbursement_benchmarking.csv")
    write_table(provider, "provider_kpis.csv")
    write_table(cost_drivers, "cost_driver_analysis.csv")
    write_table(utilization, "utilization_summary.csv")
    write_table(high_util, "high_utilization_segments.csv")
    write_table(anomalies, "anomalies.csv")
    write_table(forecast, "forecast_summary.csv")
    write_table(cms_provider_benchmarks, "cms_provider_service_benchmarks.csv")
    write_table(rate_provider, "scenario_rate_change.csv")
    write_table(util_provider, "scenario_utilization_change.csv")
    write_table(contract_provider, "scenario_provider_contract_change.csv")
    write_table(benchmark_provider, "scenario_benchmark_alignment.csv")
    write_table(scenario_summary, "scenario_summary.csv")

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
    save_scenario_plots(scenario_summary, rate_provider, util_provider, benchmark_provider, FIGURE_DIR)
    write_executive_summary(
        monthly,
        provider,
        reimbursement,
        anomalies,
        forecast,
        utilization,
        cost_drivers,
        scenario_summary,
        REPORT_DIR / "executive_summary.md",
    )
    write_excel_workbook(
        monthly,
        provider,
        reimbursement,
        utilization,
        anomalies,
        forecast,
        scenario_summary,
        rate_provider,
        util_provider,
        contract_provider,
        benchmark_provider,
        REPORT_DIR / "executive_workbook.xlsx",
    )

    print("Healthcare claims reimbursement intelligence pipeline completed.")
    print(f"Rows processed: {len(claims):,}")
    print(f"Tables written: {TABLE_DIR}")
    print(f"Figures written: {FIGURE_DIR}")
    print(f"Executive report: {REPORT_DIR / 'executive_summary.md'}")
    print(f"Excel workbook: {REPORT_DIR / 'executive_workbook.xlsx'}")
    print(f"Benchmark source: {benchmark_source}")
    print(f"CMS provider/service source: {cms_provider_source}")


if __name__ == "__main__":
    main()
