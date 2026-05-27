from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")
import matplotlib.pyplot as plt
import pandas as pd


def _exp_smoothing(values: pd.Series, alpha: float = 0.35) -> float:
    level = float(values.iloc[0])
    for value in values.iloc[1:]:
        level = alpha * float(value) + (1 - alpha) * level
    return level


def forecast_monthly_metrics(monthly: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    monthly = monthly.sort_values("service_month").copy()
    forecast_rows = []
    metrics = ["total_paid", "total_claims", "pmpm"]
    last_month = monthly["service_month"].max()
    future_months = pd.date_range(last_month + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")

    for metric in metrics:
        series = monthly[metric].astype(float)
        rolling_baseline = series.tail(3).mean()
        smoothed = _exp_smoothing(series)
        slope = (series.tail(6).iloc[-1] - series.tail(6).iloc[0]) / max(len(series.tail(6)) - 1, 1)
        for step, month in enumerate(future_months, start=1):
            forecast_value = max(0, (0.55 * smoothed) + (0.45 * rolling_baseline) + slope * step)
            forecast_rows.append(
                {
                    "forecast_month": month,
                    "metric": metric,
                    "forecast_value": forecast_value,
                    "method": "3-month rolling average + exponential smoothing",
                    "lookback_months": len(series),
                }
            )
    return pd.DataFrame(forecast_rows)


def save_forecast_plots(monthly: pd.DataFrame, forecast: pd.DataFrame, figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    metric_labels = {"total_paid": "Monthly Paid Amount", "total_claims": "Claim Volume", "pmpm": "PMPM"}
    for metric, label in metric_labels.items():
        hist = monthly[["service_month", metric]].sort_values("service_month")
        pred = forecast[forecast["metric"] == metric].sort_values("forecast_month")
        plt.figure(figsize=(9, 4.8))
        plt.plot(hist["service_month"], hist[metric], marker="o", label="Actual")
        plt.plot(pred["forecast_month"], pred["forecast_value"], marker="o", linestyle="--", label="Forecast")
        plt.title(f"{label} Forecast")
        plt.xlabel("Month")
        plt.ylabel(label)
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.savefig(figure_dir / f"forecast_{metric}.png", dpi=160)
        plt.close()
