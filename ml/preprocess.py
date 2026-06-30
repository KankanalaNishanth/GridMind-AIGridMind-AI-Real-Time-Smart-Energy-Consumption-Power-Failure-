from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_COLUMNS = {
    "Circle": "circle",
    "Division": "division",
    "SubDivision": "subdivision",
    "Section": "section",
    "Area": "area",
    "CatCode": "category_code",
    "CatDesc": "category",
    "TotServices": "total_services",
    "BilledServices": "billed_services",
    "Units": "power_consumption_kwh",
    "Load": "grid_load_kw",
}

FEATURE_COLUMNS = [
    "total_services",
    "billed_services",
    "power_consumption_kwh",
    "grid_load_kw",
    "voltage",
    "current",
    "frequency",
    "temperature_c",
    "service_utilization",
    "load_per_service",
    "hour",
    "day_of_week",
]


def load_raw_dataset(raw_dir: Path) -> pd.DataFrame:
    frames = []
    for csv_path in sorted(raw_dir.glob("*.csv")):
        frame = pd.read_csv(csv_path)
        frame["source_file"] = csv_path.name
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    data = pd.concat(frames, ignore_index=True)
    return data.rename(columns=RAW_COLUMNS)


def normalize_telemetry(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()
    for column in ["total_services", "billed_services", "power_consumption_kwh", "grid_load_kw"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)

    data["category_code"] = pd.to_numeric(data["category_code"], errors="coerce").fillna(0).astype(int)
    data["timestamp"] = pd.date_range("2026-01-01", periods=len(data), freq="15min")
    data["service_utilization"] = np.where(
        data["total_services"] > 0,
        data["billed_services"] / data["total_services"],
        0,
    )
    data["load_per_service"] = np.where(
        data["total_services"] > 0,
        data["grid_load_kw"] / data["total_services"],
        0,
    )

    # The Telangana files are aggregate load records, so these meter-like fields
    # are deterministic telemetry estimates derived from load and utilization.
    load_norm = _safe_minmax(data["grid_load_kw"])
    usage_norm = _safe_minmax(data["power_consumption_kwh"])
    data["voltage"] = (230 - (load_norm * 12) + (data["service_utilization"] * 3)).round(3)
    data["current"] = ((data["grid_load_kw"] * 1000) / data["voltage"].clip(lower=180)).round(3)
    data["frequency"] = (50 - (load_norm * 0.35)).round(3)
    data["temperature_c"] = (27 + (usage_norm * 11) + (load_norm * 5)).round(3)

    high_load = data["load_per_service"] > data["load_per_service"].quantile(0.97)
    low_voltage = data["voltage"] < 221
    poor_billing = (data["total_services"] > 30) & (data["service_utilization"] < 0.25)
    data["outage_event"] = high_load | (low_voltage & poor_billing)
    data["device_status"] = np.select(
        [data["outage_event"], low_voltage | high_load],
        ["offline", "warning"],
        default="online",
    )

    data["hour"] = data["timestamp"].dt.hour
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    return data


def prepare_training_frame(raw_dir: Path, output_path: Path | None = None) -> pd.DataFrame:
    telemetry = normalize_telemetry(load_raw_dataset(raw_dir))
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry.to_csv(output_path, index=False)
    return telemetry


def _safe_minmax(series: pd.Series) -> pd.Series:
    minimum = series.min()
    spread = series.max() - minimum
    if spread == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - minimum) / spread

