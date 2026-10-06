"""
Centralized application configuration.

All tunables (paths, thresholds, DB connection, CORS) live here and are
read from environment variables / a .env file so nothing is hardcoded
in business logic. Copy .env.example to .env and adjust as needed.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if not (BASE_DIR / "data").exists() and (BASE_DIR.parent / "data").exists():
    BASE_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "GridMind AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]

    # --- Paths (relative to project root) ---
    DATA_DIR: str = "data"
    MODELS_DIR: str = "models"
    REPORTS_DIR: str = "reports"

    # --- MongoDB ---
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "gridmind_ai"

    # --- ML pipeline params (kept identical to the original notebook) ---
    ISO_FOREST_CONTAMINATION: float = 0.05
    DISRUPTION_BILLING_RATIO_THRESHOLD: float = 0.7
    DISRUPTION_RISK_ALERT_THRESHOLD: float = 0.7
    ANOMALY_SCORE_ALERT_THRESHOLD: float = -0.1
    KMEANS_N_CLUSTERS: int = 4
    SARIMA_FORECAST_STEPS: int = 6

    @property
    def data_path(self) -> Path:
        return BASE_DIR / self.DATA_DIR

    @property
    def models_path(self) -> Path:
        return BASE_DIR / self.MODELS_DIR

    @property
    def reports_path(self) -> Path:
        return BASE_DIR / self.REPORTS_DIR


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import and call this, don't instantiate Settings() directly."""
    settings = Settings()
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.models_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)
    return settings
