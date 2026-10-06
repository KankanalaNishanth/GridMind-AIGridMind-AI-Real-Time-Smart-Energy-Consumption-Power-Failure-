"""
GridMind AI — AE (Assistant Engineer) Router
=============================================
Endpoints for authenticated AE and DE users.
AE users are scoped to their assigned division only.

PREFIX: /ae
ACCESS: AE and DE roles
SCOPE:  AE → own division_id only | DE → any division

Security:
- Role enforced via Depends(require_role("AE", "DE"))
- Division scope enforced via check_division_scope()
- Audit logging for VIEW_DATA, ACKNOWLEDGE_ALERT, UPDATE_INCIDENT
- No IDOR: division_id always taken from JWT, never trusted from request body
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.core.dependencies import (
    check_division_scope,
    get_current_user,
    get_db_dep,
    require_role,
)
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ae", tags=["AE — Assistant Engineer"])

# Convenience dependency: requires AE or DE
_ae_or_de = require_role("AE", "DE")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AcknowledgeAlertRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class UpdateIncidentRequest(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|RESOLVED|CLOSED)$")
    notes: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Helper: get effective division for current user
# ---------------------------------------------------------------------------
def _effective_division(current_user: dict, query_division: Optional[str]) -> Optional[str]:
    """Return division_id to use, enforcing AE scope. DE gets query_division as-is."""
    return check_division_scope(current_user, query_division)


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/dashboard", summary="AE division dashboard")
async def ae_dashboard(
    request: Request,
    division_id: Optional[str] = Query(None),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return dashboard data for the AE's authorized division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/dashboard:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            energy_count = db.energy_data.count_documents(query)
            anomaly_count = db.anomalies.count_documents({**query, "is_resolved": False})
            alert_count = db.alerts.count_documents({**query, "is_acknowledged": False})
            return {
                "division_id": eff_div,
                "energy_records": energy_count,
                "active_anomalies": anomaly_count,
                "unacknowledged_alerts": alert_count,
                "status": "live_db",
            }
        except Exception as exc:
            logger.warning("DB query failed ae/dashboard: %s", exc)

    return {
        "division_id": eff_div,
        "energy_records": 9256,
        "active_anomalies": 12,
        "unacknowledged_alerts": 3,
        "status": "offline_default",
    }


@router.get("/live-energy", summary="Real-time energy consumption for AE's division")
async def ae_live_energy(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return recent energy telemetry for the AE's authorized division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/live-energy:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            records = list(
                db.energy_data
                .find(query, {"_id": 0})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return {"data": records, "count": len(records), "division_id": eff_div}
        except Exception as exc:
            logger.warning("DB query failed ae/live-energy: %s", exc)

    return {"data": [], "count": 0, "division_id": eff_div, "status": "offline_default"}


@router.get("/anomalies", summary="ML-detected anomalies for AE's division")
async def ae_anomalies(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return anomalies detected by the ML models for the AE's authorized division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/anomalies:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            anomalies = list(
                db.anomalies
                .find(query, {"_id": 0})
                .sort("detected_at", -1)
                .limit(limit)
            )
            return {"anomalies": anomalies, "count": len(anomalies), "division_id": eff_div}
        except Exception as exc:
            logger.warning("DB query failed ae/anomalies: %s", exc)

    return {"anomalies": [], "count": 0, "division_id": eff_div, "status": "offline_default"}


@router.get("/predictions", summary="ML power-failure predictions for AE's division")
async def ae_predictions(
    request: Request,
    division_id: Optional[str] = Query(None),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return ML model predictions (LSTM, XGBoost, Prophet) for the AE's division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/predictions:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            preds = list(
                db.predictions
                .find(query, {"_id": 0})
                .sort("timestamp", -1)
                .limit(20)
            )
            return {"predictions": preds, "count": len(preds), "division_id": eff_div}
        except Exception as exc:
            logger.warning("DB query failed ae/predictions: %s", exc)

    return {"predictions": [], "count": 0, "division_id": eff_div, "status": "offline_default"}


@router.get("/alerts", summary="Alerts for AE's division")
async def ae_alerts(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return alerts for the AE's authorized division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/alerts:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            alerts = list(
                db.alerts
                .find(query, {"_id": 1, "alert_type": 1, "severity": 1,
                              "timestamp": 1, "message": 1, "is_acknowledged": 1})
                .sort("timestamp", -1)
                .limit(limit)
            )
            # Convert ObjectId to str
            for a in alerts:
                if "_id" in a and isinstance(a["_id"], ObjectId):
                    a["id"] = str(a.pop("_id"))
            return {"alerts": alerts, "count": len(alerts), "division_id": eff_div}
        except Exception as exc:
            logger.warning("DB query failed ae/alerts: %s", exc)

    return {"alerts": [], "count": 0, "division_id": eff_div, "status": "offline_default"}


@router.post("/alerts/{alert_id}/acknowledge", summary="Acknowledge an assigned alert")
async def ae_acknowledge_alert(
    alert_id: str,
    payload: AcknowledgeAlertRequest,
    request: Request,
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Acknowledge an alert that belongs to the AE's authorized division.
    Prevents IDOR: validates alert belongs to the user's division before acknowledging.
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")

    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Alert not found.")

    # IDOR prevention: ensure alert belongs to user's division
    eff_div = check_division_scope(current_user, None)  # get user's own division
    query: dict = {"_id": oid}
    if eff_div:  # AE: must match division; DE with no div: any
        query["division_id"] = eff_div

    alert = db.alerts.find_one(query)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Alert not found or not in your authorized division.")

    db.alerts.update_one(
        {"_id": oid},
        {"$set": {
            "is_acknowledged": True,
            "acknowledged_by": current_user["username"],
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "ack_notes": payload.notes or "",
        }},
    )

    log_audit_event(
        db,
        action="ACKNOWLEDGE_ALERT",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"alert:{alert_id}",
        user_id=current_user.get("_id"),
        details=f"Alert acknowledged. Notes: {payload.notes}",
    )

    return {"status": "acknowledged", "alert_id": alert_id}


@router.put("/incidents/{incident_id}/status", summary="Update incident status")
async def ae_update_incident(
    incident_id: str,
    payload: UpdateIncidentRequest,
    request: Request,
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Update the status of an incident in the AE's authorized division."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")

    try:
        oid = ObjectId(incident_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Incident not found.")

    eff_div = check_division_scope(current_user, None)
    query: dict = {"_id": oid}
    if eff_div:
        query["division_id"] = eff_div

    incident = db.alerts.find_one(query)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Incident not found or not in your authorized division.")

    db.alerts.update_one(
        {"_id": oid},
        {"$set": {
            "incident_status": payload.status,
            "updated_by": current_user["username"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "incident_notes": payload.notes or "",
        }},
    )

    log_audit_event(
        db,
        action="UPDATE_INCIDENT",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"incident:{incident_id}",
        user_id=current_user.get("_id"),
        details=f"Status → {payload.status}. Notes: {payload.notes}",
    )

    return {"status": "updated", "incident_id": incident_id, "new_status": payload.status}


@router.get("/history", summary="Historical energy data for AE's division")
async def ae_history(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return historical energy data for the AE's authorized division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/history:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": eff_div} if eff_div else {}
            records = list(
                db.energy_data
                .find(query, {"_id": 0})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return {"data": records, "count": len(records), "division_id": eff_div}
        except Exception as exc:
            logger.warning("DB query failed ae/history: %s", exc)

    return {"data": [], "count": 0, "division_id": eff_div, "status": "offline_default"}


@router.get("/reports", summary="Generate operational report for AE's division")
async def ae_reports(
    request: Request,
    division_id: Optional[str] = Query(None),
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Generate a summary operational report for the AE's division."""
    eff_div = _effective_division(current_user, division_id)

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/reports:{eff_div}",
        user_id=current_user.get("_id"),
    )

    report = {
        "division_id": eff_div,
        "generated_by": current_user["username"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "energy_records": 0,
            "anomalies": 0,
            "alerts": 0,
            "predictions": 0,
        },
        "status": "offline_default",
    }

    if db is not None:
        try:
            q = {"division_id": eff_div} if eff_div else {}
            report["summary"]["energy_records"] = db.energy_data.count_documents(q)
            report["summary"]["anomalies"] = db.anomalies.count_documents(q)
            report["summary"]["alerts"] = db.alerts.count_documents(q)
            report["summary"]["predictions"] = db.predictions.count_documents(q)
            report["status"] = "live_db"
        except Exception as exc:
            logger.warning("DB query failed ae/reports: %s", exc)

    return report


@router.get("/my-division", summary="Info about the AE's assigned division")
async def ae_my_division(
    request: Request,
    current_user: dict = Depends(_ae_or_de),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return information about the AE's assigned division."""
    eff_div = current_user.get("division_id")

    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"ae/my-division:{eff_div}",
        user_id=current_user.get("_id"),
    )

    if db is not None and eff_div:
        try:
            division = db.divisions.find_one({"division_id": eff_div}, {"_id": 0})
            if division:
                return division
        except Exception as exc:
            logger.warning("DB query failed ae/my-division: %s", exc)

    return {
        "division_id": eff_div,
        "name": f"Division {eff_div}" if eff_div else "All Divisions",
        "status": "offline_default",
    }
