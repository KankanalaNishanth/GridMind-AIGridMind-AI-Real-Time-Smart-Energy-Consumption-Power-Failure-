"""
Prediction endpoints backed by the pre-trained models.

All feature computation here mirrors app/services/data_loader.py exactly
so that live requests are featurized the same way the training data was.
"""
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas import AnomalyResponse, DisruptionResponse, ForecastResponse, TelemetryInput
from app.services.model_registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predict", tags=["Predictions"])


def _engineer_live_features(data: TelemetryInput) -> dict:
    billing_ratio = data.billed_services / max(data.tot_services, 1)
    avg_units = data.units / max(data.billed_services, 1)
    load_factor = data.units / max(data.load * 24 * 30, 0.1)
    return {
        "billing_ratio": billing_ratio,
        "avg_units_per_conn": avg_units,
        "load_factor": load_factor,
    }


@router.post("/disruption", response_model=DisruptionResponse)
def predict_disruption(data: TelemetryInput) -> DisruptionResponse:
    registry = get_registry()
    if registry.rf_model is None:
        raise HTTPException(503, "Disruption model not loaded — run the training pipeline first.")

    settings = get_settings()
    feats = _engineer_live_features(data)
    X = pd.DataFrame([{
        "TotServices": data.tot_services,
        "avg_units_per_conn": feats["avg_units_per_conn"],
        "load_factor": feats["load_factor"],
        "month_num": data.month_num,
        "Load": data.load,
        "billing_ratio": feats["billing_ratio"],
    }])
    prob = registry.rf_model.predict_proba(X)[0][1]
    alert = prob > settings.DISRUPTION_RISK_ALERT_THRESHOLD

    return DisruptionResponse(
        circle=data.circle,
        disruption_risk=round(float(prob), 4),
        alert=alert,
        label="HIGH" if alert else "NORMAL",
    )


@router.post("/anomaly", response_model=AnomalyResponse)
def predict_anomaly(data: TelemetryInput) -> AnomalyResponse:
    registry = get_registry()
    if registry.iso_model is None or registry.scaler_iso is None:
        raise HTTPException(503, "Anomaly model not loaded — run the training pipeline first.")

    settings = get_settings()
    feats = _engineer_live_features(data)
    X = pd.DataFrame([{
        "Units": data.units,
        "Load": data.load,
        "billing_ratio": feats["billing_ratio"],
        "avg_units_per_conn": feats["avg_units_per_conn"],
        "load_factor": feats["load_factor"],
    }])
    X_scaled = registry.scaler_iso.transform(X)
    score = registry.iso_model.score_samples(X_scaled)[0]
    is_anomaly = score < settings.ANOMALY_SCORE_ALERT_THRESHOLD

    return AnomalyResponse(
        circle=data.circle,
        anomaly_score=round(float(score), 4),
        is_anomaly=bool(is_anomaly),
    )


@router.get("/forecast", response_model=ForecastResponse)
def predict_forecast(steps: int = 6) -> ForecastResponse:
    registry = get_registry()
    settings = get_settings()
    if registry.sarima_model is None:
        raise HTTPException(503, "Forecast model not loaded — run the training pipeline first.")

    forecast = registry.sarima_model.get_forecast(steps=steps)
    fc_mean = forecast.predicted_mean

    last_month_path = settings.models_path / "sarima_last_month.txt"
    last_month = int(last_month_path.read_text().strip()) if last_month_path.exists() else 0

    points = [
        {"month": last_month + i + 1, "predicted_units": float(value)}
        for i, value in enumerate(fc_mean.values)
    ]
    return ForecastResponse(forecast_steps=steps, forecast=points)
