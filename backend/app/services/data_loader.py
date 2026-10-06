"""
Data ingestion and feature engineering.

Ports Phase 1-2 of the original GridMind AI notebook into reusable,
testable functions instead of top-level notebook cells:
  - load_raw_data(): reads every file_*.csv in the data directory
  - clean_and_engineer_features(): cleans + builds model-ready features

Both functions are deterministic and side-effect free (no plotting,
no file writes) so they can be called from the training pipeline,
from tests, or from an API route without surprises.
"""
import glob
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Circle", "Division", "SubDivision", "Section", "Area",
    "CatCode", "CatDesc", "TotServices", "BilledServices", "Units", "Load",
]


def load_raw_data(data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load and concatenate every file_*.csv found in `data_dir`
    (defaults to settings.data_path). Adds `month_num` (1-based, in
    file-sort order) and `file_name` columns, exactly as the notebook did.
    """
    settings = get_settings()
    data_dir = data_dir or settings.data_path

    pattern = str(data_dir / "file_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No CSV files matching 'file_*.csv' found in {data_dir}. "
            "Place your monthly CSV exports there before running the pipeline."
        )

    logger.info("Found %d CSV files in %s", len(files), data_dir)

    frames = []
    for i, f in enumerate(files):
        df = pd.read_csv(f)
        missing = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{os.path.basename(f)} is missing required columns: {missing}")
        df["month_num"] = i + 1
        df["file_name"] = os.path.basename(f)
        frames.append(df)
        logger.info("  [%02d] %-20s -> %d rows", i + 1, os.path.basename(f), len(df))

    master = pd.concat(frames, ignore_index=True)
    logger.info("Master DataFrame shape: %s", master.shape)
    return master


def clean_and_engineer_features(master: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw readings and engineer the model features used across all
    downstream ML models. Mirrors the notebook's Phase 2 cell exactly:
      - billing_ratio       = BilledServices / TotServices, clipped [0,1]
      - avg_units_per_conn  = Units / BilledServices (guarded against /0)
      - load_factor         = Units / (Load * 24 * 30) (guarded against /0)
      - disruption          = 1 if billing_ratio < threshold else 0
      - anomaly_zscore      = z-score of Units (EDA only, not used by IsoForest)
      - season              = derived from month_num
    """
    settings = get_settings()
    df = master.copy()

    for col in ["Units", "Load", "BilledServices", "TotServices"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    before = len(df)
    df = df[df["TotServices"] > 0].copy()
    logger.info("Dropped %d rows with TotServices <= 0", before - len(df))

    df["billing_ratio"] = (df["BilledServices"] / df["TotServices"]).clip(0, 1)
    df["avg_units_per_conn"] = np.where(
        df["BilledServices"] > 0, df["Units"] / df["BilledServices"], 0
    )
    df["load_factor"] = np.where(
        df["Load"] > 0, df["Units"] / (df["Load"] * 24 * 30), 0
    )
    df["disruption"] = (
        df["billing_ratio"] < settings.DISRUPTION_BILLING_RATIO_THRESHOLD
    ).astype(int)
    df["anomaly_zscore"] = stats.zscore(df["Units"].fillna(0))
    df["season"] = df["month_num"].apply(_month_to_season)

    logger.info(
        "Feature engineering complete. Rows=%d, Disruption rate=%.1f%%, Circles=%d",
        len(df), df["disruption"].mean() * 100, df["Circle"].nunique(),
    )
    return df


def _month_to_season(m: int) -> str:
    if m in (4, 5, 6, 13, 14):
        return "Summer"
    if m in (7, 8, 9, 15, 16):
        return "Monsoon"
    if m in (1, 2, 12):
        return "Winter"
    return "Autumn"


def load_and_prepare() -> pd.DataFrame:
    """Convenience wrapper: load raw CSVs + apply feature engineering in one call."""
    raw = load_raw_data()
    return clean_and_engineer_features(raw)
