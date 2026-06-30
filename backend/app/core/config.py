import os
from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover - lets data scripts run before dependencies are installed.
    BaseSettings = object
    SettingsConfigDict = None


class Settings(BaseSettings):
    app_name: str = "GridMind AI"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "gridmind_ai"
    kafka_bootstrap_servers: str = "localhost:9092"
    energy_topic: str = "energy-usage"
    alert_topic: str = "grid-alerts"
    forecast_topic: str = "power-forecast"
    raw_data_dir: Path = Path("data/raw")
    processed_data_path: Path = Path("data/processed/telemetry.csv")
    model_dir: Path = Path("models")

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def __init__(self, **values) -> None:
        if SettingsConfigDict is not None:
            super().__init__(**values)
            return
        self.app_name = os.getenv("APP_NAME", values.get("app_name", "GridMind AI"))
        self.api_host = os.getenv("API_HOST", values.get("api_host", "127.0.0.1"))
        self.api_port = int(os.getenv("API_PORT", values.get("api_port", 8000)))
        self.mongo_uri = os.getenv("MONGO_URI", values.get("mongo_uri", "mongodb://localhost:27017"))
        self.mongo_db = os.getenv("MONGO_DB", values.get("mongo_db", "gridmind_ai"))
        self.kafka_bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            values.get("kafka_bootstrap_servers", "localhost:9092"),
        )
        self.energy_topic = os.getenv("ENERGY_TOPIC", values.get("energy_topic", "energy-usage"))
        self.alert_topic = os.getenv("ALERT_TOPIC", values.get("alert_topic", "grid-alerts"))
        self.forecast_topic = os.getenv("FORECAST_TOPIC", values.get("forecast_topic", "power-forecast"))
        self.raw_data_dir = Path(os.getenv("RAW_DATA_DIR", values.get("raw_data_dir", "data/raw")))
        self.processed_data_path = Path(
            os.getenv("PROCESSED_DATA_PATH", values.get("processed_data_path", "data/processed/telemetry.csv"))
        )
        self.model_dir = Path(os.getenv("MODEL_DIR", values.get("model_dir", "models")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
