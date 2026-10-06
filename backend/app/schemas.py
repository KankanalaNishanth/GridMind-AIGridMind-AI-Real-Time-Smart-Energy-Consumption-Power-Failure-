"""Pydantic request/response models shared across routers."""
from typing import List, Optional

from pydantic import BaseModel, Field


class TelemetryInput(BaseModel):
    circle: str
    division: Optional[str] = None
    units: float = Field(..., ge=0, description="Energy units consumed (kWh)")
    load: float = Field(..., ge=0, description="Connected load")
    tot_services: int = Field(..., gt=0, description="Total service connections")
    billed_services: int = Field(..., ge=0, description="Billed service connections")
    month_num: int = Field(..., ge=1, description="Month index as used in training data")


class DisruptionResponse(BaseModel):
    circle: str
    disruption_risk: float
    alert: bool
    label: str


class AnomalyResponse(BaseModel):
    circle: str
    anomaly_score: float
    is_anomaly: bool


class ForecastPoint(BaseModel):
    month: int
    predicted_units: float


class ForecastResponse(BaseModel):
    forecast_steps: int
    forecast: List[ForecastPoint]


class ClusterInfo(BaseModel):
    Circle: str
    avg_units: float
    total_units: float
    avg_connections: float
    avg_billing_ratio: float
    avg_load_factor: float
    disruption_rate: float
    cluster: int


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    models_loaded: bool
    database_connected: bool


class TrainingSummary(BaseModel):
    rows_processed: int
    circles: int
    message: str = "Training pipeline completed successfully"
