"""
Model registry.

Loads every trained model artifact from disk ONCE at API startup and
keeps them in memory, instead of re-loading from disk on every request.
Routes pull models from here via `get_registry()`.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import joblib

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ModelRegistry:
    rf_model: Any = None
    iso_model: Any = None
    scaler_iso: Any = None
    sarima_model: Any = None
    kmeans_model: Any = None
    scaler_kmeans: Any = None
    loaded: bool = field(default=False)

    def is_ready(self) -> bool:
        return self.loaded and self.rf_model is not None and self.iso_model is not None


_registry = ModelRegistry()


def load_all_models() -> ModelRegistry:
    """Load all model artifacts from settings.models_path. Safe to call once at startup."""
    settings = get_settings()
    models_dir = settings.models_path

    def _try_load(filename: str) -> Optional[Any]:
        path = models_dir / filename
        if not path.exists():
            logger.warning("Model file not found: %s (train the pipeline first)", path)
            return None
        obj = joblib.load(path)
        logger.info("Loaded model: %s", filename)
        return obj

    _registry.rf_model = _try_load("rf_disruption.pkl")
    _registry.iso_model = _try_load("iso_forest.pkl")
    _registry.scaler_iso = _try_load("scaler_iso.pkl")
    _registry.sarima_model = _try_load("sarima_model.pkl")
    _registry.kmeans_model = _try_load("kmeans.pkl")
    _registry.scaler_kmeans = _try_load("scaler_kmeans.pkl")
    _registry.loaded = True

    return _registry


def get_registry() -> ModelRegistry:
    """Access the already-loaded registry. Call load_all_models() first (done in app startup)."""
    return _registry
