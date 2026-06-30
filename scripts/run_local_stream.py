from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

from backend.app.core.config import get_settings
from ml.preprocess import prepare_training_frame


def run(api_url: str, processed_path: Path, raw_dir: Path, delay: float, limit: int | None) -> None:
    if processed_path.exists():
        telemetry = pd.read_csv(processed_path, parse_dates=["timestamp"])
    else:
        telemetry = prepare_training_frame(raw_dir, processed_path)

    rows = telemetry.head(limit) if limit else telemetry
    for _, row in rows.iterrows():
        payload = row.to_dict()
        payload["timestamp"] = row["timestamp"].isoformat()
        response = requests.post(f"{api_url.rstrip('/')}/api/telemetry", json=payload, timeout=10)
        response.raise_for_status()
        print(f"posted {payload['timestamp']} {payload['circle']} {payload['area']}")
        time.sleep(delay)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Stream telemetry directly to FastAPI without Kafka.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--processed-path", type=Path, default=settings.processed_data_path)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir)
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    run(args.api_url, args.processed_path, args.raw_dir, args.delay, args.limit)


if __name__ == "__main__":
    main()

