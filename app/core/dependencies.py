"""
GridMind AI — FastAPI Dependency Injection (RBAC)
=================================================
Provides reusable FastAPI dependencies for:
- Current user resolution from JWT (get_current_user)
- Role-based access control  (require_role)
- Scope-based division access (require_ae_scope / check_division_scope)
- Database injection (get_db_dep)

Usage in routers:
    @router.get("/ae/dashboard")
    async def ae_dashboard(
        current_user = Depends(require_role("AE", "DE"))
    ):
        ...

    @router.get("/de/dashboard")
    async def de_dashboard(
        current_user = Depends(require_role("DE"))
    ):
        ...
"""
from __future__ import annotations

import logging
from typing import Optional

from bson import ObjectId
from fastapi import Depends, HTTPException, Query, Request, status
from pymongo.database import Database

from app.core.security import decode_access_token, oauth2_scheme
from app.services.db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid roles — used for documentation and validation
# ---------------------------------------------------------------------------
ROLE_AE = "AE"
ROLE_DE = "DE"
ALL_AUTHENTICATED_ROLES = {ROLE_AE, ROLE_DE}


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------

def get_db_dep() -> Optional[Database]:
    """
    FastAPI dependency that provides the active MongoDB database handle.
    Returns None if MongoDB is not connected.
    """
    return get_db()


# ---------------------------------------------------------------------------
# Token → User resolution
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Optional[Database] = Depends(get_db_dep),
) -> dict:
    """
    Decode the JWT access token and return the full user document from MongoDB.

    Raises:
        401 — token missing, invalid, or expired.
        401 — user not found in database.
        403 — account is inactive (is_active=False).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: Optional[str] = payload.get("sub")
    if not username:
        raise credentials_exception

    # Look up user in MongoDB
    if db is None:
        logger.error("MongoDB not available — cannot resolve user from token.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Please try again later.",
        )

    user = db.users.find_one({"username": username}, {"password_hash": 0})
    if user is None:
        # Log unauthorized access attempt
        _log_access_denied(db, username=username, role="unknown", ip=_get_ip(request))
        raise credentials_exception

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your Divisional Engineer.",
        )

    # Convert ObjectId to string for JSON serialization
    if "_id" in user and isinstance(user["_id"], ObjectId):
        user["_id"] = str(user["_id"])

    return user


# ---------------------------------------------------------------------------
# Role-based access dependency factory
# ---------------------------------------------------------------------------

def require_role(*roles: str):
    """
    FastAPI dependency factory for role-based authorization.

    Usage:
        Depends(require_role("AE", "DE"))  # either AE or DE
        Depends(require_role("DE"))         # DE only

    Returns the current user dict if authorized; raises 403 otherwise.
    """
    allowed = set(roles)

    async def _checker(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: Optional[Database] = Depends(get_db_dep),
    ) -> dict:
        user_role = current_user.get("role", "")
        if user_role not in allowed:
            ip = _get_ip(request)
            _log_access_denied(
                db,
                username=current_user.get("username", "unknown"),
                role=user_role,
                ip=ip,
                resource=str(request.url),
                details=f"Role '{user_role}' not in allowed roles {list(allowed)}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. This endpoint requires one of the following roles: "
                    f"{', '.join(sorted(allowed))}."
                ),
            )
        return current_user

    return _checker


# ---------------------------------------------------------------------------
# Scope / Division access guard
# ---------------------------------------------------------------------------

def check_division_scope(current_user: dict, requested_division_id: Optional[str]) -> str:
    """
    Validate that the current user is allowed to access the requested division.

    Rules:
    - DE users can access any division.
    - AE users can ONLY access their own division_id.
    - If requested_division_id is None or empty, AE gets their own division.

    Returns the effective division_id to use.

    Raises:
        403 — AE requesting a division they don't own.
    """
    role = current_user.get("role", "")
    user_division = current_user.get("division_id")

    if role == ROLE_DE:
        # DE can access any division; if none specified, return None (all divisions)
        return requested_division_id  # type: ignore[return-value]

    # AE: enforce their division only
    if not requested_division_id:
        # Return AE's own division
        return user_division  # type: ignore[return-value]

    if requested_division_id != user_division:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access denied. You are not authorized for division '{requested_division_id}'. "
                f"Your authorized division is '{user_division}'."
            ),
        )
    return requested_division_id


async def require_ae_scope(
    current_user: dict = Depends(require_role("AE", "DE")),
    division_id: Optional[str] = Query(None, description="Division ID to filter by"),
) -> tuple[dict, Optional[str]]:
    """
    Dependency that validates AE division scope from a query parameter.

    Returns (current_user, effective_division_id).
    AE users always get their own division_id regardless of the query param.
    DE users get whatever division_id is requested (or None for all).
    """
    effective_division = check_division_scope(current_user, division_id)
    return current_user, effective_division


# ---------------------------------------------------------------------------
# IDOR prevention helpers
# ---------------------------------------------------------------------------

def validate_meter_belongs_to_division(
    db: Optional[Database],
    meter_id: str,
    division_id: Optional[str],
) -> bool:
    """
    Check that a meter_id belongs to the user's authorized division.
    Returns True if authorized or if division_id is None (DE with full access).
    """
    if division_id is None:
        return True  # DE has full access
    if db is None:
        return True  # Can't validate without DB; allow with warning
    meter = db.meters.find_one({"meter_id": meter_id, "division_id": division_id})
    return meter is not None


def validate_alert_belongs_to_division(
    db: Optional[Database],
    alert_id: str,
    division_id: Optional[str],
) -> bool:
    """Check that an alert belongs to the user's authorized division."""
    if division_id is None:
        return True
    if db is None:
        return True
    try:
        oid = ObjectId(alert_id)
    except Exception:
        return False
    alert = db.alerts.find_one({"_id": oid, "division_id": division_id})
    return alert is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_ip(request: Request) -> str:
    """Extract client IP from request (handles proxies)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _log_access_denied(
    db: Optional[Database],
    username: str,
    role: str,
    ip: str,
    resource: str = "",
    details: str = "",
) -> None:
    """Write an ACCESS_DENIED event to the audit_logs collection (best-effort)."""
    if db is None:
        return
    try:
        from datetime import datetime, timezone

        db.audit_logs.insert_one({
            "user_id": None,
            "username": username,
            "role": role,
            "action": "ACCESS_DENIED",
            "resource": resource,
            "ip_address": ip,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.warning("Failed to write ACCESS_DENIED audit log: %s", exc)
