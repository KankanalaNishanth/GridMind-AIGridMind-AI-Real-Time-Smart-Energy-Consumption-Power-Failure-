from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    timestamp: datetime
    circle: str
    division: str
    subdivision: str
    section: str
    area: str
    category_code: int
    category: str
    total_services: int = Field(ge=0)
    billed_services: int = Field(ge=0)
    power_consumption_kwh: float = Field(ge=0)
    grid_load_kw: float = Field(ge=0)
    voltage: float
    current: float
    frequency: float
    temperature_c: float
    device_status: Literal["online", "warning", "offline"]
    outage_event: bool


class PredictionResult(BaseModel):
    timestamp: datetime
    demand_forecast_kwh: float
    anomaly_score: float
    is_anomaly: bool
    outage_risk: float
    recommendation: str


class DashboardSnapshot(BaseModel):
    latest: TelemetryEvent | None
    prediction: PredictionResult | None
    total_consumption_kwh: float
    average_load_kw: float
    anomaly_count: int
    outage_risk: float

