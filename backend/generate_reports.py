#!/usr/bin/env python3
"""
GridMind AI — visual reports script (Phases 3 & 11 of the original notebook).

Regenerates the EDA plots and the final 5-panel analytics dashboard as
PNG files under reports/. Purely a reporting artifact — the API itself
never needs these to serve predictions.

Run this AFTER train_pipeline.py (it loads the saved models to label
anomalies/clusters on the charts).

Usage:
    python generate_reports.py
"""
import logging
import sys

from app.core.logging_config import configure_logging
from app.services.dashboard_report import generate_final_dashboard
from app.services.data_cache import get_master_df

configure_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        df = get_master_df()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    try:
        path = generate_final_dashboard(df)
    except FileNotFoundError as exc:
        logger.error("%s (run train_pipeline.py first)", exc)
        return 1

    logger.info("Report generation complete: %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
