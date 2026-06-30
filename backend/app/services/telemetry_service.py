from __future__ import annotations

from datetime import datetime

from backend.app.db.mongo import MongoStore
from backend.app.models.schemas import DashboardSnapshot, PredictionResult, TelemetryEvent
from backend.app.services.ml_service import GridMindModelService


class TelemetryService:
    def __init__(self, store: MongoStore, model_service: GridMindModelService) -> None:
        self.store = store
        self.model_service = model_service

    def ingest(self, event: TelemetryEvent) -> PredictionResult:
        prediction = self.model_service.predict(event)
        event_doc = event.model_dump()
        prediction_doc = prediction.model_dump()
        self.store.telemetry.insert_one(event_doc)
        self.store.predictions.insert_one(prediction_doc)
        if prediction.is_anomaly or prediction.outage_risk >= 0.65:
            self.store.alerts.insert_one(
                {
                    "timestamp": prediction.timestamp,
                    "area": event.area,
                    "circle": event.circle,
                    "severity": "critical" if prediction.outage_risk >= 0.75 else "warning",
                    "message": prediction.recommendation,
                    "outage_risk": prediction.outage_risk,
                }
            )
        return prediction

    def snapshot(self) -> DashboardSnapshot:
        latest_doc = self.store.telemetry.find_one(sort=[("timestamp", -1)])
        prediction_doc = self.store.predictions.find_one(sort=[("timestamp", -1)])
        total = self._sum("power_consumption_kwh")
        avg_load = self._average("grid_load_kw")
        anomaly_count = self.store.predictions.count_documents({"is_anomaly": True})
        outage_risk = float(prediction_doc["outage_risk"]) if prediction_doc else 0
        return DashboardSnapshot(
            latest=TelemetryEvent(**_strip_id(latest_doc)) if latest_doc else None,
            prediction=PredictionResult(**_strip_id(prediction_doc)) if prediction_doc else None,
            total_consumption_kwh=round(total, 3),
            average_load_kw=round(avg_load, 3),
            anomaly_count=anomaly_count,
            outage_risk=round(outage_risk, 4),
        )

    def recent_telemetry(self, limit: int = 100) -> list[dict]:
        docs = list(self.store.telemetry.find(sort=[("timestamp", -1)], limit=limit))
        return [_serialize_doc(doc) for doc in reversed(docs)]

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        docs = list(self.store.alerts.find(sort=[("timestamp", -1)], limit=limit))
        return [_serialize_doc(doc) for doc in docs]

    def history_report(self, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
        match = {}
        if start or end:
            match["timestamp"] = {}
            if start:
                match["timestamp"]["$gte"] = start
            if end:
                match["timestamp"]["$lte"] = end
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$circle",
                    "records": {"$sum": 1},
                    "consumption_kwh": {"$sum": "$power_consumption_kwh"},
                    "average_load_kw": {"$avg": "$grid_load_kw"},
                    "outages": {"$sum": {"$cond": ["$outage_event", 1, 0]}},
                }
            },
            {"$sort": {"consumption_kwh": -1}},
        ]
        return [_serialize_doc(doc) for doc in self.store.telemetry.aggregate(pipeline)]

    def _sum(self, field: str) -> float:
        result = list(self.store.telemetry.aggregate([{"$group": {"_id": None, "value": {"$sum": f"${field}"}}}]))
        return float(result[0]["value"]) if result else 0

    def _average(self, field: str) -> float:
        result = list(self.store.telemetry.aggregate([{"$group": {"_id": None, "value": {"$avg": f"${field}"}}}]))
        return float(result[0]["value"]) if result and result[0]["value"] is not None else 0


def _strip_id(doc: dict | None) -> dict:
    if not doc:
        return {}
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _serialize_doc(doc: dict) -> dict:
    doc = _strip_id(doc)
    for key, value in list(doc.items()):
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

