from __future__ import annotations

import argparse
import json

import requests
from kafka import KafkaConsumer

from backend.app.core.config import get_settings


def consume_events(api_url: str) -> None:
    settings = get_settings()
    consumer = KafkaConsumer(
        settings.energy_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="gridmind-fastapi-consumer",
    )
    for message in consumer:
        response = requests.post(f"{api_url.rstrip('/')}/api/telemetry", json=message.value, timeout=10)
        response.raise_for_status()
        print(f"processed {message.value['timestamp']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume Kafka telemetry and forward it to FastAPI.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    consume_events(args.api_url)


if __name__ == "__main__":
    main()

