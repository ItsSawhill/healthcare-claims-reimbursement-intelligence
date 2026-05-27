from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _base_summary(frame: pd.DataFrame, scenario_name: str, simulated_paid_col: str) -> dict:
    baseline_paid = frame["baseline_paid_amount"].sum()
    simulated_paid = frame[simulated_paid_col].sum()
    member_months = frame["member_months"].max()
    dollar_impact = simulated_paid - baseline_paid
    return {
        "scenario_name": scenario_name,
        "baseline_paid_amount": baseline_paid,
        "simulated_paid_amount": simulated_paid,
        "dollar_impact": dollar_impact,
        "percent_impact": dollar_impact / baseline_paid if baseline_paid else 0,
        "pmpm_impact": dollar_impact / member_months if member_months else 0,
        "member_months": member_months,
    }


def _provider_rollup(frame: pd.DataFrame, simulated_paid_col: str, scenario_name: str) -> pd.DataFrame:
    provider = frame.groupby(["provider_id", "provider_name", "service_category"], dropna=False).agg(
        baseline_paid_amount=("baseline_paid_amount", "sum"),
        simulated_paid_amount=(simulated_paid_col, "sum"),
        baseline_benchmark_variance=("baseline_benchmark_variance", "sum"),
        simulated_benchmark_variance=("simulated_benchmark_variance", "sum"),
        member_months=("member_months", "max"),
        total_claims=("claim_id", "count"),
    )
    provider["dollar_impact"] = provider["simulated_paid_amount"] - provider["baseline_paid_amount"]
    provider["percent_impact"] = provider["dollar_impact"] / provider["baseline_paid_amount"].replace(0, pd.NA)
    provider["pmpm_impact"] = provider["dollar_impact"] / provider["member_months"].replace(0, pd.NA)
    provider["benchmark_variance_impact"] = (
        provider["simulated_benchmark_variance"] - provider["baseline_benchmark_variance"]
    )
    provider["scenario_name"] = scenario_name
    provider["risk_rank"] = provider["dollar_impact"].abs().rank(method="dense", ascending=False).astype(int)
    return provider.reset_index().sort_values("risk_rank")


def _service_rollup(frame: pd.DataFrame, simulated_paid_col: str, scenario_name: str) -> pd.DataFrame:
    service = frame.groupby("service_category", dropna=False).agg(
        baseline_paid_amount=("baseline_paid_amount", "sum"),
        simulated_paid_amount=(simulated_paid_col, "sum"),
        baseline_benchmark_variance=("baseline_benchmark_variance", "sum"),
        simulated_benchmark_variance=("simulated_benchmark_variance", "sum"),
        member_months=("member_months", "max"),
        total_claims=("claim_id", "count"),
    )
    service["dollar_impact"] = service["simulated_paid_amount"] - service["baseline_paid_amount"]
    service["percent_impact"] = service["dollar_impact"] / service["baseline_paid_amount"].replace(0, pd.NA)
    service["pmpm_impact"] = service["dollar_impact"] / service["member_months"].replace(0, pd.NA)
    service["benchmark_variance_impact"] = service["simulated_benchmark_variance"] - service["baseline_benchmark_variance"]
    service["scenario_name"] = scenario_name
    return service.reset_index().sort_values("dollar_impact", key=lambda s: s.abs(), ascending=False)


def _claim_frame(claims: pd.DataFrame) -> pd.DataFrame:
    frame = claims.copy()
    frame["baseline_paid_amount"] = frame["paid_amount"]
    frame["baseline_benchmark_variance"] = frame["allowed_amount"] - frame["medicare_benchmark_amount"]
    return frame


def simulate_reimbursement_rate_change(claims: pd.DataFrame, rate_change: float = 0.05) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_name = f"Reimbursement rate change {rate_change:+.0%}"
    frame = _claim_frame(claims)
    frame["simulated_paid_amount"] = np.where(
        frame["denial_flag"].eq(1),
        0,
        (frame["paid_amount"] * (1 + rate_change)).clip(lower=0),
    )
    frame["simulated_allowed_amount"] = np.where(
        frame["denial_flag"].eq(1),
        frame["allowed_amount"],
        (frame["allowed_amount"] * (1 + rate_change)).clip(lower=0),
    )
    frame["simulated_benchmark_variance"] = frame["simulated_allowed_amount"] - frame["medicare_benchmark_amount"]
    provider = _provider_rollup(frame, "simulated_paid_amount", scenario_name)
    service = _service_rollup(frame, "simulated_paid_amount", scenario_name)
    provider["scenario_type"] = "rate_change"
    service["scenario_type"] = "rate_change"
    return provider, service


def simulate_utilization_change(claims: pd.DataFrame, utilization_change: float = 0.10) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_name = f"Utilization change {utilization_change:+.0%}"
    frame = _claim_frame(claims)
    frame["simulated_paid_amount"] = frame["paid_amount"] * (1 + utilization_change)
    frame["simulated_allowed_amount"] = frame["allowed_amount"] * (1 + utilization_change)
    frame["simulated_benchmark_variance"] = frame["simulated_allowed_amount"] - frame["medicare_benchmark_amount"]
    provider = _provider_rollup(frame, "simulated_paid_amount", scenario_name)
    service = _service_rollup(frame, "simulated_paid_amount", scenario_name)
    provider["scenario_type"] = "utilization_change"
    service["scenario_type"] = "utilization_change"
    return provider, service


def simulate_provider_contract_change(
    claims: pd.DataFrame,
    provider_ids: list[str] | None = None,
    contract_change: float = -0.05,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if provider_ids is None:
        top_providers = claims.groupby("provider_id")["paid_amount"].sum().nlargest(5).index.tolist()
        provider_ids = top_providers
    scenario_name = f"Provider contract change {contract_change:+.0%}"
    frame = _claim_frame(claims)
    affected = frame["provider_id"].isin(provider_ids)
    frame["simulated_paid_amount"] = frame["paid_amount"]
    frame.loc[affected & frame["denial_flag"].eq(0), "simulated_paid_amount"] = (
        frame.loc[affected & frame["denial_flag"].eq(0), "paid_amount"] * (1 + contract_change)
    ).clip(lower=0)
    frame["simulated_allowed_amount"] = frame["allowed_amount"]
    frame.loc[affected & frame["denial_flag"].eq(0), "simulated_allowed_amount"] = (
        frame.loc[affected & frame["denial_flag"].eq(0), "allowed_amount"] * (1 + contract_change)
    ).clip(lower=0)
    frame["simulated_benchmark_variance"] = frame["simulated_allowed_amount"] - frame["medicare_benchmark_amount"]
    provider = _provider_rollup(frame, "simulated_paid_amount", scenario_name)
    provider["affected_provider_flag"] = provider["provider_id"].isin(provider_ids).astype(int)
    service = _service_rollup(frame, "simulated_paid_amount", scenario_name)
    provider["scenario_type"] = "provider_contract_change"
    service["scenario_type"] = "provider_contract_change"
    return provider, service


def simulate_benchmark_alignment(claims: pd.DataFrame, alignment_rate: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_name = f"Benchmark alignment {alignment_rate:.0%}"
    frame = _claim_frame(claims)
    target_allowed = frame["medicare_benchmark_amount"] * alignment_rate
    paid_ratio = frame["paid_amount"] / frame["allowed_amount"].replace(0, pd.NA)
    frame["simulated_allowed_amount"] = np.where(frame["denial_flag"].eq(1), frame["allowed_amount"], target_allowed)
    frame["simulated_paid_amount"] = np.where(
        frame["denial_flag"].eq(1),
        0,
        (frame["simulated_allowed_amount"] * paid_ratio.fillna(0)).clip(lower=0),
    )
    frame["simulated_benchmark_variance"] = frame["simulated_allowed_amount"] - frame["medicare_benchmark_amount"]
    provider = _provider_rollup(frame, "simulated_paid_amount", scenario_name)
    service = _service_rollup(frame, "simulated_paid_amount", scenario_name)
    provider["scenario_type"] = "benchmark_alignment"
    service["scenario_type"] = "benchmark_alignment"
    return provider, service


def generate_scenario_summary(
    rate_change_provider: pd.DataFrame,
    utilization_provider: pd.DataFrame,
    contract_provider: pd.DataFrame,
    benchmark_provider: pd.DataFrame,
) -> pd.DataFrame:
    scenarios = [
        ("Rate Change +5%", rate_change_provider),
        ("Utilization +10%", utilization_provider),
        ("Top Provider Contract -5%", contract_provider),
        ("Medicare Benchmark Alignment", benchmark_provider),
    ]
    rows = []
    for scenario_name, frame in scenarios:
        baseline_paid = frame["baseline_paid_amount"].sum()
        simulated_paid = frame["simulated_paid_amount"].sum()
        dollar_impact = simulated_paid - baseline_paid
        member_months = frame["member_months"].max()
        top_provider = frame.sort_values("dollar_impact", key=lambda s: s.abs(), ascending=False).iloc[0]
        rows.append(
            {
                "scenario_name": scenario_name,
                "baseline_paid_amount": baseline_paid,
                "simulated_paid_amount": simulated_paid,
                "dollar_impact": dollar_impact,
                "percent_impact": dollar_impact / baseline_paid if baseline_paid else 0,
                "pmpm_impact": dollar_impact / member_months if member_months else 0,
                "benchmark_variance_impact": (
                    frame["simulated_benchmark_variance"].sum() - frame["baseline_benchmark_variance"].sum()
                ),
                "top_affected_provider": top_provider["provider_name"],
                "top_affected_provider_id": top_provider["provider_id"],
                "top_provider_dollar_impact": top_provider["dollar_impact"],
            }
        )
    return pd.DataFrame(rows)


def save_scenario_plots(
    summary: pd.DataFrame,
    rate_change: pd.DataFrame,
    utilization: pd.DataFrame,
    benchmark: pd.DataFrame,
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(summary["scenario_name"], summary["dollar_impact"], color="#2f6f8f")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Scenario Financial Impact", fontsize=14, weight="bold")
    ax.set_xlabel("Dollar Impact vs Baseline")
    fig.tight_layout()
    fig.savefig(figure_dir / "scenario_financial_impact.png", dpi=180)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(summary["scenario_name"], summary["pmpm_impact"], color="#1f7a5c")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Scenario PMPM Impact", fontsize=14, weight="bold")
    ax.set_ylabel("PMPM Impact")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(figure_dir / "scenario_pmpm_impact.png", dpi=180)
    plt.close()

    exposure = pd.concat([rate_change, utilization], ignore_index=True)
    exposure = exposure.groupby(["provider_id", "provider_name"]).agg(dollar_impact=("dollar_impact", "sum")).reset_index()
    exposure = exposure.sort_values("dollar_impact", key=lambda s: s.abs(), ascending=False).head(12).sort_values("dollar_impact")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(exposure["provider_name"], exposure["dollar_impact"], color="#9b5f31")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Provider Scenario Exposure", fontsize=14, weight="bold")
    ax.set_xlabel("Combined Rate and Utilization Impact")
    fig.tight_layout()
    fig.savefig(figure_dir / "provider_scenario_exposure.png", dpi=180)
    plt.close()

    bench = benchmark.sort_values("benchmark_variance_impact", key=lambda s: s.abs(), ascending=False).head(12)
    bench = bench.sort_values("benchmark_variance_impact")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(bench["provider_name"], bench["benchmark_variance_impact"], color="#744c7d")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Benchmark Alignment Impact", fontsize=14, weight="bold")
    ax.set_xlabel("Benchmark Variance Impact")
    fig.tight_layout()
    fig.savefig(figure_dir / "benchmark_alignment_impact.png", dpi=180)
    plt.close()
