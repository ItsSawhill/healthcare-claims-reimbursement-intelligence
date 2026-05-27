from pathlib import Path

import pandas as pd


REQUIRED_CMS_COLUMNS = {"procedure_code", "benchmark_amount", "year"}
OPTIONAL_CMS_COLUMNS = {"locality", "state"}


def load_cms_benchmark_file(path: Path | str | None) -> pd.DataFrame | None:
    """Load a local CMS benchmark CSV when one is available.

    The pipeline does not depend on external CMS calls. This loader supports a
    local export from CMS public data resources and returns None when no local
    file is configured.
    """
    if path is None:
        return None

    benchmark_path = Path(path)
    if not benchmark_path.exists():
        return None

    benchmark = pd.read_csv(benchmark_path)
    missing = REQUIRED_CMS_COLUMNS.difference(benchmark.columns)
    if missing:
        raise ValueError(f"CMS benchmark file is missing required columns: {sorted(missing)}")

    benchmark = benchmark.copy()
    benchmark["procedure_code"] = benchmark["procedure_code"].astype(str)
    benchmark["benchmark_amount"] = pd.to_numeric(benchmark["benchmark_amount"], errors="coerce")
    benchmark["year"] = pd.to_numeric(benchmark["year"], errors="coerce").astype("Int64")
    benchmark = benchmark.dropna(subset=["procedure_code", "benchmark_amount", "year"])
    benchmark = benchmark[benchmark["benchmark_amount"] >= 0]

    for column in OPTIONAL_CMS_COLUMNS.difference(benchmark.columns):
        benchmark[column] = pd.NA
    return benchmark


def apply_cms_or_fallback_benchmarks(claims: pd.DataFrame, cms_path: Path | str | None = None) -> tuple[pd.DataFrame, str]:
    """Apply local CMS benchmarks by procedure code, or retain synthetic benchmarks."""
    cms_benchmarks = load_cms_benchmark_file(cms_path)
    enriched = claims.copy()

    if cms_benchmarks is None or cms_benchmarks.empty:
        enriched["benchmark_source"] = "synthetic_medicare_style"
        return enriched, "synthetic_medicare_style"

    latest_year = cms_benchmarks["year"].max()
    latest = cms_benchmarks[cms_benchmarks["year"] == latest_year]
    latest = latest.sort_values(["procedure_code", "benchmark_amount"]).drop_duplicates("procedure_code", keep="last")
    latest = latest[["procedure_code", "benchmark_amount", "year"]].rename(
        columns={"benchmark_amount": "cms_benchmark_amount", "year": "cms_benchmark_year"}
    )

    enriched = enriched.merge(latest, on="procedure_code", how="left")
    matched = enriched["cms_benchmark_amount"].notna()
    if matched.any():
        enriched.loc[matched, "medicare_benchmark_amount"] = enriched.loc[matched, "cms_benchmark_amount"]
        enriched.loc[matched, "benchmark_source"] = "local_cms_file"
        enriched.loc[~matched, "benchmark_source"] = "synthetic_medicare_style"
    else:
        enriched["benchmark_source"] = "synthetic_medicare_style"
    enriched = enriched.drop(columns=["cms_benchmark_amount", "cms_benchmark_year"], errors="ignore")
    return enriched, "local_cms_file"
