#!/usr/bin/env python3
"""
GridMind AI — full training pipeline (production script version of the notebook).

Loads all monthly CSVs from data/, cleans + engineers features, trains
every model (Isolation Forest, Random Forest, SARIMA, Prophet, KMeans),
and saves all artifacts to models/. Run this once before starting the
API, and again any time you refresh the underlying data.

Usage (from the project root, with your venv activated):
    python train_pipeline.py
"""
import json
import logging
import sys
import time

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.services.data_loader import load_and_prepare
from app.services.ml_pipeline import run_full_pipeline

configure_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    start = time.time()

    logger.info("=" * 60)
    logger.info("  GRIDMIND AI — TRAINING PIPELINE")
    logger.info("=" * 60)

    try:
        df = load_and_prepare()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    summary = run_full_pipeline(df)
    elapsed = time.time() - start

    logger.info("=" * 60)
    logger.info("  TRAINING COMPLETE in %.1fs", elapsed)
    logger.info("  Rows processed : %d", summary["rows_processed"])
    logger.info("  Circles        : %d", summary["circles"])
    logger.info("  RF ROC-AUC     : %.4f", summary["random_forest"]["roc_auc"])
    logger.info("  Anomalies      : %d (%.1f%%)",
                 summary["isolation_forest"]["anomalies_detected"],
                 summary["isolation_forest"]["anomaly_rate_pct"])
    logger.info("  Saved to       : %s", settings.models_path)
    logger.info("=" * 60)

    # Write a machine-readable summary too, useful for CI or a dashboard
    summary_path = settings.reports_path / "training_summary.json"
    with open(summary_path, "w") as f:
        json.dump(
            {k: v for k, v in summary.items() if k != "random_forest"} | {
                "random_forest": {"roc_auc": summary["random_forest"]["roc_auc"]}
            },
            f, indent=2, default=str,
        )
    logger.info("  Summary written to %s", summary_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
