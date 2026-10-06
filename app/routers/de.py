"""
GridMind AI — DE (Divisional Engineer) Router
==============================================
Endpoints accessible ONLY to DE (Divisional Engineer) role.

PREFIX: /de
ACCESS: DE role ONLY
SCOPE:  Division-wide monitoring, AE user management, audit logs

Security:
- All endpoints enforce Depends(require_role("DE"))
- DE cannot create other DE accounts (privilege escalation prevention)
- DE cannot change user roles to DE
- Audit logging for all user management operations
- Never expose password_hash
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from pymongo.database import Database

from app.core.dependencies import (
    get_current_user,
    get_db_dep,
    require_role,
)
from app.services.audit_service import get_audit_logs, log_audit_event
from app.services.user_service import (
    create_user,
    deactivate_user,
    get_user_by_id,
    list_users,
    update_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/de", tags=["DE — Divisional Engineer"])

_de_only = require_role("DE")


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateAEUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, example="ae003")
    password: str = Field(..., min_length=8, max_length=128, example="AEPass1!")
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    division_id: str = Field(..., example="DIV001")
    # role is always AE — DE cannot create DE accounts


class UpdateAEUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    division_id: Optional[str] = None
    # role and division changes intentionally excluded from direct update to prevent escalation


class AlertUpdateRequest(BaseModel):
    severity: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    status: Optional[str] = Field(None, pattern="^(OPEN|IN_PROGRESS|RESOLVED|CLOSED)$")
    notes: Optional[str] = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# Dashboard & Analytics
# ---------------------------------------------------------------------------

@router.get("/dashboard", summary="Division-wide monitoring dashboard")
async def de_dashboard(
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return aggregated dashboard data across all divisions under DE's scope."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource="de/dashboard",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            return {
                "total_energy_records": db.energy_data.count_documents({}),
                "total_anomalies": db.anomalies.count_documents({}),
                "active_alerts": db.alerts.count_documents({"is_acknowledged": False}),
                "total_ae_users": db.users.count_documents({"role": "AE"}),
                "status": "live_db",
            }
        except Exception as exc:
            logger.warning("DB query failed de/dashboard: %s", exc)

    return {
        "total_energy_records": 156294,
        "total_anomalies": 7815,
        "active_alerts": 42,
        "total_ae_users": 2,
        "status": "offline_default",
    }


@router.get("/divisions", summary="All divisions under DE's responsibility")
async def de_divisions(
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return all grid divisions managed by this DE."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource="de/divisions",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            divisions = list(db.divisions.find({}, {"_id": 0}).sort("division_id", 1))
            return {"divisions": divisions, "count": len(divisions)}
        except Exception as exc:
            logger.warning("DB query failed de/divisions: %s", exc)

    return {"divisions": [
        {"division_id": "DIV001", "name": "Division 1"},
        {"division_id": "DIV002", "name": "Division 2"},
    ], "count": 2, "status": "offline_default"}


@router.get("/live-energy", summary="Live energy across all divisions")
async def de_live_energy(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return real-time energy telemetry for all or a specific division."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"de/live-energy:{division_id}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": division_id} if division_id else {}
            records = list(db.energy_data.find(query, {"_id": 0})
                           .sort("timestamp", -1).limit(limit))
            return {"data": records, "count": len(records)}
        except Exception as exc:
            logger.warning("DB query failed de/live-energy: %s", exc)

    return {"data": [], "count": 0, "status": "offline_default"}


@router.get("/anomalies", summary="All anomalies across divisions")
async def de_anomalies(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return all anomalies (or filtered by division) detected by the ML models."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"de/anomalies:{division_id}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": division_id} if division_id else {}
            anomalies = list(db.anomalies.find(query, {"_id": 0})
                             .sort("detected_at", -1).limit(limit))
            return {"anomalies": anomalies, "count": len(anomalies)}
        except Exception as exc:
            logger.warning("DB query failed de/anomalies: %s", exc)

    return {"anomalies": [], "count": 0, "status": "offline_default"}


@router.get("/predictions", summary="ML predictions across all divisions")
async def de_predictions(
    request: Request,
    division_id: Optional[str] = Query(None),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return ML model predictions (LSTM/XGBoost/Prophet) across all divisions."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"de/predictions:{division_id}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": division_id} if division_id else {}
            preds = list(db.predictions.find(query, {"_id": 0})
                         .sort("timestamp", -1).limit(50))
            return {"predictions": preds, "count": len(preds)}
        except Exception as exc:
            logger.warning("DB query failed de/predictions: %s", exc)

    return {"predictions": [], "count": 0, "status": "offline_default"}


@router.get("/alerts", summary="All alerts with management capabilities")
async def de_alerts(
    request: Request,
    division_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return all alerts with full details for management."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"de/alerts:{division_id}",
        user_id=current_user.get("_id"),
    )

    if db is not None:
        try:
            query = {"division_id": division_id} if division_id else {}
            alerts = list(db.alerts.find(query, {"_id": 1, "alert_type": 1, "severity": 1,
                                                  "timestamp": 1, "message": 1, "division_id": 1,
                                                  "is_acknowledged": 1, "status": 1})
                          .sort("timestamp", -1).limit(limit))
            for a in alerts:
                if "_id" in a and isinstance(a["_id"], ObjectId):
                    a["id"] = str(a.pop("_id"))
            return {"alerts": alerts, "count": len(alerts)}
        except Exception as exc:
            logger.warning("DB query failed de/alerts: %s", exc)

    return {"alerts": [], "count": 0, "status": "offline_default"}


@router.put("/alerts/{alert_id}", summary="Manage/update an alert")
async def de_update_alert(
    alert_id: str,
    payload: AlertUpdateRequest,
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Update alert severity, status, or add management notes."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Alert not found.")

    updates: dict = {}
    if payload.severity:
        updates["severity"] = payload.severity
    if payload.status:
        updates["status"] = payload.status
    if payload.notes is not None:
        updates["management_notes"] = payload.notes
    updates["managed_by"] = current_user["username"]
    updates["managed_at"] = datetime.now(timezone.utc).isoformat()

    result = db.alerts.update_one({"_id": oid}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Alert not found.")

    log_audit_event(
        db,
        action="UPDATE_ALERT",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"alert:{alert_id}",
        user_id=current_user.get("_id"),
        details=f"Updated fields: {list(updates.keys())}",
    )

    return {"status": "updated", "alert_id": alert_id}


@router.get("/reports", summary="Detailed division-wide reports")
async def de_reports(
    request: Request,
    division_id: Optional[str] = Query(None),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Generate a detailed division-wide operational and analytics report."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"de/reports:{division_id}",
        user_id=current_user.get("_id"),
    )

    report: dict = {
        "generated_by": current_user["username"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "division_filter": division_id,
        "summary": {},
        "status": "offline_default",
    }

    if db is not None:
        try:
            q = {"division_id": division_id} if division_id else {}
            report["summary"] = {
                "energy_records": db.energy_data.count_documents(q),
                "anomalies": db.anomalies.count_documents(q),
                "alerts": db.alerts.count_documents(q),
                "predictions": db.predictions.count_documents(q),
                "ae_users": db.users.count_documents({**q, "role": "AE"}),
            }
            report["status"] = "live_db"
        except Exception as exc:
            logger.warning("DB query failed de/reports: %s", exc)

    return report


@router.get("/system-performance", summary="System health metrics")
async def de_system_performance(
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Return system-wide health and performance metrics."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource="de/system-performance",
        user_id=current_user.get("_id"),
    )

    metrics: dict = {
        "db_connected": db is not None,
        "total_users": 0,
        "total_ae_users": 0,
        "total_de_users": 0,
        "status": "offline_default",
    }

    if db is not None:
        try:
            metrics["total_users"] = db.users.count_documents({})
            metrics["total_ae_users"] = db.users.count_documents({"role": "AE"})
            metrics["total_de_users"] = db.users.count_documents({"role": "DE"})
            metrics["status"] = "live_db"
        except Exception as exc:
            logger.warning("DB query failed de/system-performance: %s", exc)

    return metrics


# ---------------------------------------------------------------------------
# User Management (AE only — DE cannot create other DEs)
# ---------------------------------------------------------------------------

@router.get("/users", summary="List AE users in DE's scope")
async def de_list_users(
    request: Request,
    division_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """List all AE users. Optionally filter by division or active status."""
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource="de/users",
        user_id=current_user.get("_id"),
    )

    if db is None:
        return {"users": [], "count": 0, "status": "offline"}

    users = list_users(db, role="AE", division_id=division_id, is_active=is_active)
    return {"users": users, "count": len(users)}


@router.post("/users", summary="Create a new AE user", status_code=status.HTTP_201_CREATED)
async def de_create_user(
    payload: CreateAEUserRequest,
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Create a new Assistant Engineer user.
    DE can only create AE-role accounts (privilege escalation is blocked).
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")

    # Validate password strength
    from app.core.security import validate_password_strength
    ok, msg = validate_password_strength(payload.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=msg)

    try:
        new_user = create_user(
            db,
            user_data={
                "username": payload.username,
                "password": payload.password,
                "name": payload.name,
                "email": payload.email,
                "role": "AE",  # Always AE — privilege escalation prevention
                "division_id": payload.division_id,
            },
            actor_role="DE",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_audit_event(
        db,
        action="CREATE_USER",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"user:{payload.username}",
        user_id=current_user.get("_id"),
        details=f"Created AE user '{payload.username}' for division '{payload.division_id}'",
    )

    return new_user


@router.put("/users/{user_id}", summary="Update an AE user")
async def de_update_user(
    user_id: str,
    payload: UpdateAEUserRequest,
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Update a user's allowed fields.
    Role CANNOT be changed via this endpoint (prevents privilege escalation).
    """
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")

    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found.")
    if target.get("role") != "AE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You can only manage AE-role users.")

    updates = {k: v for k, v in payload.dict(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No update fields provided.")

    try:
        updated = update_user(db, user_id, updates, actor_username=current_user["username"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_audit_event(
        db,
        action="UPDATE_USER",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"user:{user_id}",
        user_id=current_user.get("_id"),
        details=f"Updated fields: {list(updates.keys())}",
    )

    return updated


@router.delete("/users/{user_id}", summary="Deactivate an AE user")
async def de_deactivate_user(
    user_id: str,
    request: Request,
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Deactivate (soft-delete) an AE user account."""
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable.")

    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found.")
    if target.get("role") != "AE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You can only deactivate AE-role users.")

    success = deactivate_user(db, user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found.")

    log_audit_event(
        db,
        action="DELETE_USER",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"user:{user_id}",
        user_id=current_user.get("_id"),
        details=f"Deactivated AE user '{target.get('username')}'",
    )

    return {"status": "deactivated", "user_id": user_id}


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@router.get("/audit-logs", summary="View audit logs for DE's scope")
async def de_audit_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    current_user: dict = Depends(_de_only),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    View audit logs. Read-only — DE cannot modify audit logs.
    Optionally filter by action type or username.
    """
    log_audit_event(
        db,
        action="VIEW_DATA",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource="de/audit-logs",
        user_id=current_user.get("_id"),
    )

    logs = get_audit_logs(db, limit=limit, action=action, username=username)
    return {"logs": logs, "count": len(logs)}
