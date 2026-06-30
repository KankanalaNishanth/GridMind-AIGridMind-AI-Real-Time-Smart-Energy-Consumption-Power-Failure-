from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from backend.app.core.config import get_settings
from backend.app.models.schemas import PredictionResult, TelemetryEvent


class GridMindModelService:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = model_dir or get_settings().model_dir
        self.forecast_model = self._load_joblib("demand_forecast.joblib")
        self.anomaly_model = self._load_joblib("anomaly_detector.joblib")
        self.features = self._load_features()

    @property
    def ready(self) -> bool:
        return self.forecast_model is not None and self.anomaly_model is not None

    def predict(self, event: TelemetryEvent) -> PredictionResult:
        frame = pd.DataFrame([self._features_from_event(event)])
        if self.ready:
            demand_forecast = float(max(self.forecast_model.predict(frame[self.features])[0], 0))
            anomaly_raw = int(self.anomaly_model.predict(frame[self.features])[0])
            anomaly_score = float(-self.anomaly_model.decision_function(frame[self.features])[0])
            is_anomaly = anomaly_raw == -1
        else:
            demand_forecast = event.power_consumption_kwh * 1.03
            anomaly_score = self._heuristic_risk(event)
            is_anomaly = anomaly_score > 0.68

        outage_risk = min(max((anomaly_score * 0.55) + self._heuristic_risk(event), 0), 1)
        return PredictionResult(
            timestamp=event.timestamp,
            demand_forecast_kwh=round(demand_forecast, 3),
            anomaly_score=round(anomaly_score, 4),
            is_anomaly=is_anomaly,
            outage_risk=round(outage_risk, 4),
            recommendation=self._recommend(event, outage_risk, is_anomaly),
        )

    def _load_joblib(self, name: str):
        path = self.model_dir / name
        if not path.exists():
            return None
        return joblib.load(path)

    def _load_features(self) -> list[str]:
        path = self.model_dir / "features.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _features_from_event(self, event: TelemetryEvent) -> dict:
        utilization = event.billed_services / event.total_services if event.total_services else 0
        load_per_service = event.grid_load_kw / event.total_services if event.total_services else 0
        return {
            "total_services": event.total_services,
            "billed_services": event.billed_services,
            "power_consumption_kwh": event.power_consumption_kwh,
            "grid_load_kw": event.grid_load_kw,
            "voltage": event.voltage,
            "current": event.current,
            "frequency": event.frequency,
            "temperature_c": event.temperature_c,
            "service_utilization": utilization,
            "load_per_service": load_per_service,
            "hour": event.timestamp.hour,
            "day_of_week": event.timestamp.weekday(),
        }

    def _heuristic_risk(self, event: TelemetryEvent) -> float:
        voltage_risk = max(0, 225 - event.voltage) / 35
        frequency_risk = max(0, 49.8 - event.frequency) / 1.0
        load_risk = min(event.grid_load_kw / 5000, 1)
        status_risk = 0.35 if event.device_status == "warning" else 0.75 if event.device_status == "offline" else 0
        return min((voltage_risk + frequency_risk + load_risk + status_risk) / 2.6, 1)

    def _recommend(self, event: TelemetryEvent, risk: float, is_anomaly: bool) -> str:
        if risk >= 0.75:
            return f"Dispatch inspection for {event.area}; reduce non-critical load and check transformer stress."
        if is_anomaly:
            return f"Review abnormal consumption in {event.area}; compare billed services with feeder load."
        if event.power_consumption_kwh > 10000:
            return "Shift flexible demand to off-peak slots and notify high-load consumers."
        return "Grid conditions look stable; continue normal monitoring."

