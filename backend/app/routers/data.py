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

import pandas as pd
from app.services.data_cache import get_master_df

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["Data"])


@router.get("/consumption")
def get_consumption(circle: Optional[str] = None, limit: int = Query(100, le=1000)):
    db = get_db()
    if db is not None:
        try:
            query = {"circle": circle} if circle else {}
            records = list(db.telemetry.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit))
            return {"data": records, "count": len(records), "source": "mongodb"}
        except Exception as e:
            logger.warning("MongoDB read failed: %s", e)

    # Graceful fallback: return top rows from master dataset
    try:
        df = get_master_df()
        if circle:
            df_filtered = df[df["Circle"].str.upper() == circle.upper()]
        else:
            df_filtered = df
        sample = df_filtered.head(limit).copy()
        sample["timestamp"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        records = sample.to_dict(orient="records")
        return {"data": records, "count": len(records), "source": "csv_cache"}
    except Exception as e:
        logger.error("Failed to load fallback consumption data: %s", e)
        raise HTTPException(503, "Database not connected and cached data unavailable.")


@router.get("/alerts")
def get_alerts(limit: int = Query(50, le=1000)):
    db = get_db()
    if db is not None:
        try:
            alerts = list(db.alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
            return {"alerts": alerts, "count": len(alerts), "source": "mongodb"}
        except Exception as e:
            logger.warning("MongoDB alert read failed: %s", e)

    # Graceful fallback: return disruptions from master dataset
    try:
        df = get_master_df()
        disruptions = df[df["disruption"] == 1].head(limit).copy()
        disruptions["timestamp"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        disruptions["alert_type"] = "Power Disruption Alert"
        disruptions["severity"] = "HIGH"
        records = disruptions.to_dict(orient="records")
        return {"alerts": records, "count": len(records), "source": "csv_cache"}
    except Exception as e:
        logger.error("Failed to load fallback alerts data: %s", e)
        raise HTTPException(503, "Database not connected and alert data unavailable.")
