"""
Kafka stream simulation (Phase 9 of the original notebook).

Simulates a producer publishing telemetry readings and a consumer
running them through the trained models in real time, using an
in-memory queue — no real Kafka broker required. This is a local
replay/demo tool for testing the ML scoring path end-to-end.

For a real deployment, swap `deque`-based queues for `kafka-python`
Producer/Consumer objects against an actual broker; the message
shape and scoring logic (`consume_and_predict`) stay the same —
that's the whole point of separating them out here.
"""
import logging
from collections import deque
from typing import Any

import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)

KAFKA_TOPIC = "energy_telemetry"
PREDICTIONS_TOPIC = "predictions"


def produce_messages(df: pd.DataFrame, queue: deque, n: int = 20, random_state: int = None) -> int:
    """Simulate a Kafka producer: sample `n` rows and publish them as JSON-like dicts."""
    sample = df.sample(n=min(n, len(df)), random_state=random_state)
    for _, row in sample.iterrows():
        msg = {
            "timestamp": str(pd.Timestamp.now()),
            "circle": row["Circle"],
            "division": row.get("Division", ""),
            "units": float(row["Units"]),
            "load": float(row["Load"]),
            "tot_services": int(row["TotServices"]),
            "billed_services": int(row["BilledServices"]),
            "billing_ratio": float(row["billing_ratio"]),
            "month_num": int(row["month_num"]),
        }
        queue.append(msg)
    logger.info("[PRODUCER] Published %d messages to topic: %s", len(sample), KAFKA_TOPIC)
    return len(sample)


def consume_and_predict(queue: deque, rf_model: Any, iso_model: Any, scaler: Any) -> list[dict]:
    """Simulate a Kafka consumer: drain the queue, score each message with the trained models."""
    settings = get_settings()
    results = []

    while queue:
        msg = queue.popleft()

        billed = max(msg["billed_services"], 1)
        load = max(msg["load"], 0.1)

        clf_X = pd.DataFrame([{
            "TotServices": msg["tot_services"],
            "avg_units_per_conn": msg["units"] / billed,
            "load_factor": msg["units"] / (load * 24 * 30),
            "month_num": msg["month_num"],
            "Load": msg["load"],
            "billing_ratio": msg["billing_ratio"],
        }])
        disruption_risk = rf_model.predict_proba(clf_X)[0][1]

        iso_X = pd.DataFrame([{
            "Units": msg["units"],
            "Load": msg["load"],
            "billing_ratio": msg["billing_ratio"],
            "avg_units_per_conn": msg["units"] / billed,
            "load_factor": msg["units"] / (load * 24 * 30),
        }])
        iso_scaled = scaler.transform(iso_X)
        anomaly_score = iso_model.score_samples(iso_scaled)[0]
        is_anomaly = anomaly_score < settings.ANOMALY_SCORE_ALERT_THRESHOLD

        prediction = {
            **msg,
            "disruption_risk": round(float(disruption_risk), 4),
            "anomaly_score": round(float(anomaly_score), 4),
            "is_anomaly": bool(is_anomaly),
            "alert": bool(disruption_risk > settings.DISRUPTION_RISK_ALERT_THRESHOLD or is_anomaly),
        }
        results.append(prediction)

    logger.info(
        "[CONSUMER] Processed %d messages, %d alerts generated",
        len(results), sum(p["alert"] for p in results),
    )
    return results


def run_simulation(df: pd.DataFrame, rf_model: Any, iso_model: Any, scaler: Any, n: int = 30) -> list[dict]:
    """Convenience wrapper: produce N sample messages, then consume + score them."""
    message_queue: deque = deque(maxlen=1000)
    produce_messages(df, message_queue, n=n)
    return consume_and_predict(message_queue, rf_model, iso_model, scaler)
