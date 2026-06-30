from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

from backend.app.core.config import get_settings
from ml.preprocess import prepare_training_frame


def stream_events(processed_path: Path, raw_dir: Path, delay: float, limit: int | None) -> None:
    settings = get_settings()
    if processed_path.exists():
        telemetry = pd.read_csv(processed_path, parse_dates=["timestamp"])
    else:
        telemetry = prepare_training_frame(raw_dir, processed_path)

    producer = KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
    )
    rows = telemetry.head(limit) if limit else telemetry
    for _, row in rows.iterrows():
        payload = row.to_dict()
        payload["timestamp"] = row["timestamp"].isoformat()
        producer.send(settings.energy_topic, payload)
        producer.flush()
        print(f"sent {payload['timestamp']} {payload['circle']} {payload['area']}")
        time.sleep(delay)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Stream normalized energy telemetry into Kafka.")
    parser.add_argument("--processed-path", type=Path, default=settings.processed_data_path)
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_data_dir)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    stream_events(args.processed_path, args.raw_dir, args.delay, args.limit)


if __name__ == "__main__":
    main()

