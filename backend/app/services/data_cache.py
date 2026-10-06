"""
Lazy, process-wide cache for the cleaned+engineered master DataFrame.

Training, evaluation, reporting, and the Kafka simulator all need the
same featurized dataset. Loading and feature-engineering 156k rows is
cheap (~1s) but there's no reason to repeat it — load once, reuse.
"""
import logging
from typing import Optional

import pandas as pd

from app.services.data_loader import load_and_prepare

logger = logging.getLogger(__name__)

_cached_df: Optional[pd.DataFrame] = None


def get_master_df(force_reload: bool = False) -> pd.DataFrame:
    global _cached_df
    if _cached_df is None or force_reload:
        logger.info("Loading and featurizing master dataset (cache %s)...",
                     "miss" if _cached_df is None else "forced reload")
        _cached_df = load_and_prepare()
    return _cached_df
