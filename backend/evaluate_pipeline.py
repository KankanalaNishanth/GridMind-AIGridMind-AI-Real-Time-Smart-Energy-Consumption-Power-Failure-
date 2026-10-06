#!/usr/bin/env python3
"""
GridMind AI — model evaluation script (Phase 8 of the original notebook).

Reloads every saved model from models/ and recomputes its evaluation
metrics (accuracy, ROC-AUC, MAE/RMSE/MAPE, silhouette score), prints a
summary, and writes reports/evaluation_summary.json.

Run this AFTER train_pipeline.py.

Usage:
    python evaluate_pipeline.py
"""
import json
import logging
import sys

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.services.data_cache import get_master_df
from app.services.evaluation import evaluate_all_models

configure_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()

    try:
        df = get_master_df()
        summary = evaluate_all_models(df)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    out_path = settings.reports_path / "evaluation_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("Evaluation summary written to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
