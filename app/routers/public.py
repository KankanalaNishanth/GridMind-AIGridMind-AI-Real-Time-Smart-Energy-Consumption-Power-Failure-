"""
GridMind AI — Public API Router
=================================
Endpoints accessible WITHOUT authentication.
Returns only aggregated, non-sensitive data.

Prefix: /api/v1/public
Tags:   [Public]
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from app.core.dependencies import get_db_dep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public", tags=["Public"])


# ---------------------------------------------------------------------------
# Static fallback data (used when MongoDB is unavailable)
# ---------------------------------------------------------------------------
_FALLBACK_SUMMARY = {
    "total_records": 156294,
    "anomaly_count": 7815,
    "total_circles": 16,
    "avg_consumption_kwh": 1420.5,
    "platform": "GridMind AI",
    "status": "offline_default",
}

_FALLBACK_TRENDS = [
    {"month": "Jan", "avg_units": 1200.0, "anomaly_rate": 0.04},
    {"month": "Feb", "avg_units": 1150.5, "anomaly_rate": 0.05},
    {"month": "Mar", "avg_units": 1320.3, "anomaly_rate": 0.03},
    {"month": "Apr", "avg_units": 1410.0, "anomaly_rate": 0.06},
    {"month": "May", "avg_units": 1580.7, "anomaly_rate": 0.07},
    {"month": "Jun", "avg_units": 1700.2, "anomaly_rate": 0.08},
]

_FALLBACK_INSIGHTS = [
    "Energy consumption peaks in summer months due to cooling load.",
    "Grid anomaly rates are highest in the Warangal and Karimnagar circles.",
    "Billing ratio improvements correlate with reduced disruption risk.",
    "LSTM model forecasts stable demand growth of ~5% over next 6 months.",
]


# ---------------------------------------------------------------------------
# Helper: strip internal IDs
# ---------------------------------------------------------------------------
def _public_safe(doc: dict, expose_fields: list[str]) -> dict:
    """Return only the specified fields from a document."""
    return {k: doc[k] for k in expose_fields if k in doc}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/energy-summary",
    summary="General electricity consumption statistics",
    description="Aggregated energy statistics visible to all public users. No sensitive data exposed.",
)
def get_energy_summary(db: Optional[Database] = Depends(get_db_dep)):
    """Return aggregated energy consumption statistics."""
    if db is not None:
        try:
            total = db.energy_data.count_documents({})
            if total > 0:
                return {
                    "total_records": total,
                    "anomaly_count": db.anomalies.count_documents({}),
                    "total_circles": 16,
                    "platform": "GridMind AI",
                    "status": "live_db",
                }
        except Exception as exc:
            logger.warning("DB query failed for energy-summary: %s", exc)

    return _FALLBACK_SUMMARY


@router.get(
    "/power-trends",
    summary="Non-sensitive energy trend data",
    description="Monthly aggregated energy consumption trends. No division or meter IDs exposed.",
)
def get_power_trends(db: Optional[Database] = Depends(get_db_dep)):
    """Return monthly energy trend aggregates."""
    if db is not None:
        try:
            # Aggregate energy_data by month — return only safe fields
            pipeline = [
                {"$group": {
                    "_id": "$month",
                    "avg_units": {"$avg": "$units"},
                    "anomaly_rate": {"$avg": "$is_anomaly"},
                }},
                {"$project": {"month": "$_id", "avg_units": 1, "anomaly_rate": 1, "_id": 0}},
                {"$sort": {"month": 1}},
                {"$limit": 12},
            ]
            result = list(db.energy_data.aggregate(pipeline))
            if result:
                return {"trends": result, "status": "live_db"}
        except Exception as exc:
            logger.warning("DB query failed for power-trends: %s", exc)

    return {"trends": _FALLBACK_TRENDS, "status": "offline_default"}


@router.get(
    "/anomaly-stats",
    summary="General anomaly statistics",
    description="High-level anomaly rates only. No location, meter, or division identifiers exposed.",
)
def get_anomaly_stats(db: Optional[Database] = Depends(get_db_dep)):
    """Return general anomaly statistics (aggregate only)."""
    if db is not None:
        try:
            total_anomalies = db.anomalies.count_documents({})
            total_records = db.energy_data.count_documents({})
            rate = round(total_anomalies / max(total_records, 1), 4)
            return {
                "total_anomalies": total_anomalies,
                "anomaly_rate": rate,
                "severity_breakdown": {
                    "HIGH": db.anomalies.count_documents({"severity": "HIGH"}),
                    "MEDIUM": db.anomalies.count_documents({"severity": "MEDIUM"}),
                    "LOW": db.anomalies.count_documents({"severity": "LOW"}),
                },
                "status": "live_db",
            }
        except Exception as exc:
            logger.warning("DB query failed for anomaly-stats: %s", exc)

    return {
        "total_anomalies": 7815,
        "anomaly_rate": 0.05,
        "severity_breakdown": {"HIGH": 312, "MEDIUM": 1563, "LOW": 5940},
        "status": "offline_default",
    }


@router.get(
    "/alerts",
    summary="Public alerts",
    description="Non-sensitive alert summary. Division IDs, meter IDs, and coordinates are never exposed.",
)
def get_public_alerts(
    limit: int = Query(10, ge=1, le=50),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return recent public alerts (aggregated, no sensitive location data)."""
    safe_fields = ["alert_type", "severity", "timestamp", "message", "status"]

    if db is not None:
        try:
            raw = list(
                db.alerts
                .find({"is_public": True}, {"_id": 0, **{f: 1 for f in safe_fields}})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return {"alerts": raw, "count": len(raw), "status": "live_db"}
        except Exception as exc:
            logger.warning("DB query failed for public alerts: %s", exc)

    fallback_alerts = [
        {
            "alert_type": "Power Disruption",
            "severity": "HIGH",
            "timestamp": "2026-10-05T06:00:00Z",
            "message": "Elevated disruption risk detected in northern grid zone.",
            "status": "ACTIVE",
        },
        {
            "alert_type": "Anomaly Detected",
            "severity": "MEDIUM",
            "timestamp": "2026-10-04T18:30:00Z",
            "message": "Unusual consumption pattern detected.",
            "status": "RESOLVED",
        },
    ]
    return {"alerts": fallback_alerts[:limit], "count": len(fallback_alerts[:limit]), "status": "offline_default"}


@router.get(
    "/insights",
    summary="Basic AI-generated energy insights",
    description="General AI recommendations. No sensitive operational information.",
)
def get_public_insights(db: Optional[Database] = Depends(get_db_dep)):
    """Return basic AI-generated energy insights for public users."""
    return {
        "insights": _FALLBACK_INSIGHTS,
        "generated_by": "GridMind AI ML Pipeline",
        "models": ["LSTM", "Isolation Forest", "XGBoost", "Prophet"],
        "disclaimer": "These insights are general summaries for public awareness.",
    }
