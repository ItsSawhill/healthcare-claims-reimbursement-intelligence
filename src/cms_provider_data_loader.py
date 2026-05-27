from pathlib import Path

import pandas as pd


CMS_PROVIDER_SOURCE = "CMS Medicare Physician & Other Practitioners public data"
SIMULATED_SOURCE = "simulated"


COLUMN_ALIASES = {
    "provider_npi": [
        "provider_npi",
        "npi",
        "rndrng_npi",
        "rendering_npi",
        "national_provider_identifier",
    ],
    "provider_name": [
        "provider_name",
        "rndrng_prvdr_last_org_name",
        "rendering_provider_name",
        "provider_last_name_organization_name",
    ],
    "provider_first_name": [
        "provider_first_name",
        "rndrng_prvdr_first_name",
        "rendering_provider_first_name",
    ],
    "provider_state": [
        "provider_state",
        "state",
        "rndrng_prvdr_state_abrvtn",
        "rendering_provider_state",
    ],
    "procedure_code": [
        "procedure_code",
        "hcpcs_code",
        "hcpcs_cd",
        "hcpcs",
    ],
    "service_description": [
        "service_description",
        "hcpcs_description",
        "hcpcs_desc",
        "description",
    ],
    "number_of_services": [
        "number_of_services",
        "tot_srvcs",
        "total_services",
        "services",
        "line_srvc_cnt",
    ],
    "submitted_charge_amount": [
        "submitted_charge_amount",
        "avg_sbmtd_chrg",
        "average_submitted_charge_amount",
        "average_submitted_charge",
    ],
    "medicare_allowed_amount": [
        "medicare_allowed_amount",
        "avg_mdcr_alowd_amt",
        "average_medicare_allowed_amount",
        "average_medicare_allowed",
    ],
    "medicare_payment_amount": [
        "medicare_payment_amount",
        "avg_mdcr_pymt_amt",
        "average_medicare_payment_amount",
        "average_medicare_payment",
    ],
}


REQUIRED_STANDARD_COLUMNS = {
    "provider_npi",
    "provider_name",
    "provider_state",
    "procedure_code",
    "service_description",
    "number_of_services",
    "submitted_charge_amount",
    "medicare_allowed_amount",
    "medicare_payment_amount",
}


def _normalize_column_name(column: str) -> str:
    normalized = column.strip().lower()
    for char in [" ", "-", "/", ".", "(", ")", "$"]:
        normalized = normalized.replace(char, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _standardize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame.columns = [_normalize_column_name(column) for column in frame.columns]
    rename_map = {}
    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_column_name(alias)
            if normalized_alias in frame.columns:
                rename_map[normalized_alias] = standard_name
                break
    frame = frame.rename(columns=rename_map)

    if "provider_name" not in frame.columns and {"provider_first_name", "provider_name"}.issubset(frame.columns):
        frame["provider_name"] = frame["provider_name"].fillna("") + ", " + frame["provider_first_name"].fillna("")
    elif "provider_name" in frame.columns and "provider_first_name" in frame.columns:
        has_first = frame["provider_first_name"].notna() & frame["provider_first_name"].astype(str).str.len().gt(0)
        frame.loc[has_first, "provider_name"] = (
            frame.loc[has_first, "provider_name"].astype(str) + ", " + frame.loc[has_first, "provider_first_name"].astype(str)
        )
    return frame


def load_cms_provider_service_data(path: Path | str | None) -> pd.DataFrame | None:
    if path is None:
        print("CMS provider/service benchmark file not configured; using simulated benchmark fallback.")
        return None

    source_path = Path(path)
    if not source_path.exists():
        print(f"CMS provider/service benchmark file not found at {source_path}; using simulated benchmark fallback.")
        return None

    raw = pd.read_csv(source_path)
    standardized = _standardize_columns(raw)
    missing = REQUIRED_STANDARD_COLUMNS.difference(standardized.columns)
    if missing:
        raise ValueError(f"CMS provider/service file is missing required columns after standardization: {sorted(missing)}")

    selected = standardized[list(REQUIRED_STANDARD_COLUMNS)].copy()
    selected["provider_npi"] = selected["provider_npi"].astype(str)
    selected["provider_name"] = selected["provider_name"].astype(str).str.strip()
    selected["provider_state"] = selected["provider_state"].astype(str).str.upper().str.strip()
    selected["procedure_code"] = selected["procedure_code"].astype(str).str.strip()
    selected["service_description"] = selected["service_description"].astype(str).str.strip()

    numeric_cols = [
        "number_of_services",
        "submitted_charge_amount",
        "medicare_allowed_amount",
        "medicare_payment_amount",
    ]
    for col in numeric_cols:
        selected[col] = pd.to_numeric(selected[col], errors="coerce")
    selected = selected.dropna(subset=["procedure_code", "number_of_services"])
    selected = selected[selected["number_of_services"] > 0]

    selected["avg_submitted_charge"] = selected["submitted_charge_amount"]
    selected["avg_medicare_allowed"] = selected["medicare_allowed_amount"]
    selected["avg_medicare_payment"] = selected["medicare_payment_amount"]
    selected["medicare_payment_to_charge_ratio"] = (
        selected["avg_medicare_payment"] / selected["avg_submitted_charge"].replace(0, pd.NA)
    )
    selected["allowed_to_charge_ratio"] = selected["avg_medicare_allowed"] / selected["avg_submitted_charge"].replace(0, pd.NA)
    return selected


def _weighted_benchmark(frame: pd.DataFrame, group_cols: list[str], benchmark_level: str) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        services = group["number_of_services"].sum()
        row = dict(zip(group_cols, keys))
        row.update(
            {
                "benchmark_level": benchmark_level,
                "number_of_services": services,
                "avg_submitted_charge": (group["avg_submitted_charge"] * group["number_of_services"]).sum() / services,
                "avg_medicare_allowed": (group["avg_medicare_allowed"] * group["number_of_services"]).sum() / services,
                "avg_medicare_payment": (group["avg_medicare_payment"] * group["number_of_services"]).sum() / services,
            }
        )
        rows.append(row)
    output = pd.DataFrame(rows)
    output["medicare_payment_to_charge_ratio"] = output["avg_medicare_payment"] / output["avg_submitted_charge"].replace(0, pd.NA)
    output["allowed_to_charge_ratio"] = output["avg_medicare_allowed"] / output["avg_submitted_charge"].replace(0, pd.NA)
    return output


def create_cms_provider_service_benchmarks(cms_provider_service: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "benchmark_level",
        "procedure_code",
        "provider_state",
        "service_category",
        "service_description",
        "number_of_services",
        "avg_submitted_charge",
        "avg_medicare_allowed",
        "avg_medicare_payment",
        "medicare_payment_to_charge_ratio",
        "allowed_to_charge_ratio",
    ]
    if cms_provider_service is None or cms_provider_service.empty:
        return pd.DataFrame(columns=columns)

    frame = cms_provider_service.copy()
    procedure = _weighted_benchmark(frame, ["procedure_code"], "procedure_code")
    description = frame.groupby("procedure_code")["service_description"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
    procedure = procedure.merge(description.rename("service_description"), on="procedure_code", how="left")

    state = _weighted_benchmark(frame, ["provider_state"], "provider_state")
    service_category = _weighted_benchmark(frame.assign(service_category="CMS Provider Services"), ["service_category"], "service_category")

    for data in [procedure, state, service_category]:
        for column in columns:
            if column not in data.columns:
                data[column] = pd.NA
    return pd.concat([procedure[columns], state[columns], service_category[columns]], ignore_index=True)


def enrich_claims_with_cms_provider_benchmarks(
    claims: pd.DataFrame,
    cms_benchmarks: pd.DataFrame | None,
) -> tuple[pd.DataFrame, str]:
    enriched = claims.copy()
    cms_columns = [
        "cms_avg_submitted_charge",
        "cms_avg_medicare_allowed",
        "cms_avg_medicare_payment",
        "cms_allowed_variance",
        "cms_payment_variance",
        "cms_benchmark_source",
    ]

    if cms_benchmarks is None or cms_benchmarks.empty:
        if "benchmark_source" not in enriched.columns:
            enriched["benchmark_source"] = SIMULATED_SOURCE
        else:
            enriched["benchmark_source"] = enriched["benchmark_source"].fillna(SIMULATED_SOURCE)
        enriched["cms_benchmark_source"] = SIMULATED_SOURCE
        for column in cms_columns[:-1]:
            enriched[column] = pd.NA
        return enriched, SIMULATED_SOURCE

    procedure_benchmarks = cms_benchmarks[cms_benchmarks["benchmark_level"] == "procedure_code"][
        ["procedure_code", "avg_submitted_charge", "avg_medicare_allowed", "avg_medicare_payment"]
    ].rename(
        columns={
            "avg_submitted_charge": "cms_avg_submitted_charge",
            "avg_medicare_allowed": "cms_avg_medicare_allowed",
            "avg_medicare_payment": "cms_avg_medicare_payment",
        }
    )
    enriched = enriched.merge(procedure_benchmarks, on="procedure_code", how="left")
    matched = enriched["cms_avg_medicare_allowed"].notna()
    enriched["cms_allowed_variance"] = enriched["allowed_amount"] - enriched["cms_avg_medicare_allowed"]
    enriched["cms_payment_variance"] = enriched["paid_amount"] - enriched["cms_avg_medicare_payment"]
    enriched["cms_benchmark_source"] = SIMULATED_SOURCE
    enriched.loc[matched, "cms_benchmark_source"] = CMS_PROVIDER_SOURCE
    enriched["benchmark_source"] = SIMULATED_SOURCE
    enriched.loc[matched, "benchmark_source"] = CMS_PROVIDER_SOURCE
    enriched.loc[matched, "medicare_benchmark_amount"] = enriched.loc[matched, "cms_avg_medicare_allowed"]
    return enriched, CMS_PROVIDER_SOURCE if matched.any() else SIMULATED_SOURCE
