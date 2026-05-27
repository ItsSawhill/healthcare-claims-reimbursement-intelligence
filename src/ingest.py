from pathlib import Path

import numpy as np
import pandas as pd


RAW_PATH = Path("data/raw/claims.csv")
SAMPLE_PATH = Path("data/sample/synthetic_claims_sample.csv")


def generate_synthetic_claims(n_rows: int = 20000, seed: int = 42) -> pd.DataFrame:
    """Create a realistic claims file with benchmark rates and injected anomalies."""
    rng = np.random.default_rng(seed)
    months = pd.date_range("2024-01-01", "2025-12-01", freq="MS")

    providers = pd.DataFrame(
        {
            "provider_id": [f"PRV{i:03d}" for i in range(1, 41)],
            "provider_name": [f"Provider Group {i:02d}" for i in range(1, 41)],
            "region": rng.choice(["Northeast", "Midwest", "South", "West"], 40, p=[0.24, 0.22, 0.34, 0.20]),
            "provider_risk_factor": rng.normal(1.0, 0.16, 40).clip(0.72, 1.45),
        }
    )
    providers.loc[providers.provider_id.isin(["PRV004", "PRV017"]), "provider_risk_factor"] *= 1.45

    service_categories = ["Inpatient", "Outpatient", "Professional", "Emergency", "Pharmacy", "Imaging", "Lab"]
    category_base = {
        "Inpatient": 8200,
        "Outpatient": 1650,
        "Professional": 380,
        "Emergency": 1950,
        "Pharmacy": 260,
        "Imaging": 780,
        "Lab": 120,
    }
    diagnosis_codes = ["E11", "I10", "J44", "M54", "R07", "N18", "F32", "Z00", "C50", "K21", "O80"]
    procedure_codes = ["99213", "99214", "93000", "80053", "71046", "70551", "27447", "45378", "J3490", "A0429"]
    payers = ["Commercial", "Medicare Advantage", "Managed Medicaid", "Exchange"]
    payer_allowed = {"Commercial": 0.72, "Medicare Advantage": 0.58, "Managed Medicaid": 0.47, "Exchange": 0.64}

    month_idx = rng.integers(0, len(months), n_rows)
    service_month = months[month_idx]
    seasonal = 1 + 0.09 * np.sin((service_month.month.to_numpy() - 1) / 12 * 2 * np.pi)
    trend = 1 + 0.012 * month_idx

    provider_rows = providers.iloc[rng.integers(0, len(providers), n_rows)].reset_index(drop=True)
    service = rng.choice(service_categories, n_rows, p=[0.10, 0.22, 0.30, 0.09, 0.14, 0.08, 0.07])
    payer = rng.choice(payers, n_rows, p=[0.47, 0.25, 0.18, 0.10])
    base = np.array([category_base[c] for c in service])
    billed = rng.lognormal(mean=np.log(base * seasonal * trend * provider_rows.provider_risk_factor), sigma=0.45)
    billed = billed.clip(45, 85000)

    benchmark = billed * rng.normal(0.55, 0.07, n_rows).clip(0.38, 0.72)
    allowed = billed * np.array([payer_allowed[p] for p in payer]) * rng.normal(1.0, 0.08, n_rows)
    allowed = np.minimum(allowed, billed * 0.92).clip(20)

    denial_probability = (
        0.035
        + np.where(service == "Emergency", 0.025, 0)
        + np.where(service == "Inpatient", 0.018, 0)
        + np.where(payer == "Managed Medicaid", 0.025, 0)
    )
    denied = rng.random(n_rows) < denial_probability
    member_resp = allowed * rng.uniform(0.02, 0.18, n_rows)
    paid = np.where(denied, 0, (allowed - member_resp) * rng.normal(0.98, 0.025, n_rows))
    paid = paid.clip(0)

    # Inject clear business anomalies: excessive billing, denial spike, reimbursement drop, PMPM spike.
    high_bill_mask = (provider_rows.provider_id == "PRV004") & (service == "Outpatient") & (service_month >= "2025-05-01")
    billed[high_bill_mask] *= 2.8
    allowed[high_bill_mask] *= 1.55
    paid[high_bill_mask & ~denied] *= 1.45

    denial_spike_mask = (provider_rows.provider_id == "PRV017") & (service_month >= "2025-07-01")
    denied[denial_spike_mask] = rng.random(denial_spike_mask.sum()) < 0.34
    paid[denial_spike_mask & denied] = 0

    reimbursement_drop_mask = (provider_rows.provider_id == "PRV029") & (service_month >= "2025-09-01")
    allowed[reimbursement_drop_mask] *= 0.62
    paid[reimbursement_drop_mask & ~denied] *= 0.55

    pmpm_spike_mask = (service_month == "2025-11-01") & np.isin(service, ["Inpatient", "Emergency"])
    billed[pmpm_spike_mask] *= 1.65
    allowed[pmpm_spike_mask] *= 1.45
    paid[pmpm_spike_mask & ~denied] *= 1.38

    paid_date = service_month + pd.to_timedelta(rng.integers(7, 75, n_rows), unit="D")
    member_months = 8800 + (month_idx * 28) + rng.integers(-170, 170, n_rows)

    df = pd.DataFrame(
        {
            "claim_id": [f"CLM{i:07d}" for i in range(1, n_rows + 1)],
            "member_id": [f"MBR{x:06d}" for x in rng.integers(1, 9000, n_rows)],
            "provider_id": provider_rows.provider_id,
            "provider_name": provider_rows.provider_name,
            "service_date": service_month + pd.to_timedelta(rng.integers(0, 28, n_rows), unit="D"),
            "paid_date": paid_date,
            "diagnosis_code": rng.choice(diagnosis_codes, n_rows),
            "procedure_code": rng.choice(procedure_codes, n_rows),
            "service_category": service,
            "billed_amount": billed.round(2),
            "allowed_amount": allowed.round(2),
            "paid_amount": paid.round(2),
            "member_responsibility": member_resp.round(2),
            "denial_flag": denied.astype(int),
            "region": provider_rows.region,
            "payer": payer,
            "member_months": member_months,
            "medicare_benchmark_amount": benchmark.round(2),
        }
    )
    return df


def load_or_create_claims(raw_path: Path = RAW_PATH, n_rows: int = 20000) -> pd.DataFrame:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        return pd.read_csv(raw_path, parse_dates=["service_date", "paid_date"])
    df = generate_synthetic_claims(n_rows=n_rows)
    df.to_csv(raw_path, index=False)
    df.head(500).to_csv(SAMPLE_PATH, index=False)
    return df
