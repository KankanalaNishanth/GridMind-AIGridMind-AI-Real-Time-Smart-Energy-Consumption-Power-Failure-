"""
Data access endpoints — reads live telemetry/alerts from MongoDB.

These collections (`telemetry`, `alerts`) are populated by whatever
ingestion process feeds your production system (e.g. a Kafka consumer
calling /predict/* and writing results here). This router only reads.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["Data"])


@router.get("/consumption")
def get_consumption(circle: Optional[str] = None, limit: int = Query(100, le=1000)):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database not connected.")

    query = {"circle": circle} if circle else {}
    records = list(db.telemetry.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit))
    return {"data": records, "count": len(records)}


@router.get("/alerts")
def get_alerts(limit: int = Query(50, le=1000)):
    db = get_db()
    if db is None:
        raise HTTPException(503, "Database not connected.")

    alerts = list(db.alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
    return {"alerts": alerts, "count": len(alerts)}
