"""
GridMind AI — Common Authenticated Endpoints
=============================================
Endpoints available to ALL authenticated users (AE and DE).

PREFIX: /common
ACCESS: AE and DE roles

SECURITY:
- Role/division_id cannot be changed via PUT /profile
- Password change requires verification of current password
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from pymongo.database import Database

from app.core.dependencies import get_current_user, get_db_dep, require_role
from app.core.security import validate_password_strength
from app.services.audit_service import log_audit_event
from app.services.user_service import change_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/common", tags=["Common — Authenticated Users"])

_auth = require_role("AE", "DE")


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UpdateProfileRequest(BaseModel):
    """Only safe profile fields. Role and division_id are intentionally excluded."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class ProfileResponse(BaseModel):
    username: str
    name: str
    email: str
    role: str
    division_id: Optional[str] = None
    is_active: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=ProfileResponse, summary="Get current user's profile")
async def get_profile(
    current_user: dict = Depends(_auth),
):
    """Return the authenticated user's own profile (no sensitive fields)."""
    return ProfileResponse(
        username=current_user["username"],
        name=current_user.get("name", ""),
        email=current_user.get("email", ""),
        role=current_user["role"],
        division_id=current_user.get("division_id"),
        is_active=current_user.get("is_active", True),
    )


@router.put("/profile", response_model=ProfileResponse, summary="Update own profile")
async def update_profile(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: dict = Depends(_auth),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Update own name and email only.

    SECURITY: role, division_id, username, and is_active CANNOT be
    changed via this endpoint — even if a client sends those fields.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        )

    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot identify user.")

    # Explicit whitelist — role/division_id are NOT in this dict
    safe_updates: dict = {}
    if payload.name is not None:
        safe_updates["name"] = payload.name.strip()
    if payload.email is not None:
        safe_updates["email"] = str(payload.email).strip().lower()

    if not safe_updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No valid fields to update.")

    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid user ID.")

    db.users.update_one({"_id": oid}, {"$set": safe_updates})

    log_audit_event(
        db,
        action="UPDATE_USER",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"user:{user_id}",
        user_id=user_id,
        details=f"Profile self-update: {list(safe_updates.keys())}",
    )

    updated = db.users.find_one({"_id": oid}, {"password_hash": 0})
    if updated and "_id" in updated and isinstance(updated["_id"], ObjectId):
        updated["_id"] = str(updated["_id"])

    return ProfileResponse(
        username=updated["username"] if updated else current_user["username"],
        name=updated.get("name", "") if updated else safe_updates.get("name", ""),
        email=updated.get("email", "") if updated else safe_updates.get("email", ""),
        role=current_user["role"],  # role cannot change
        division_id=current_user.get("division_id"),  # division cannot change
        is_active=updated.get("is_active", True) if updated else True,
    )


@router.post("/change-password", summary="Change own password")
async def change_own_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(_auth),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Change the authenticated user's own password.
    Requires verification of the current (old) password.
    """
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        )

    # Validate new password strength
    ok, msg = validate_password_strength(payload.new_password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=msg,
        )

    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot identify user.")

    try:
        change_password(
            db,
            user_id=user_id,
            new_password=payload.new_password,
            old_password=payload.old_password,
            require_old=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    log_audit_event(
        db,
        action="CHANGE_PASSWORD",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=_get_ip(request),
        resource=f"user:{user_id}",
        user_id=user_id,
        details="User changed their own password.",
    )

    return {"status": "success", "message": "Password updated successfully."}


@router.get("/notifications", summary="User's own notifications")
async def get_notifications(
    current_user: dict = Depends(_auth),
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Return notifications for the authenticated user only.
    IDOR-safe: queries strictly by current_user's _id.
    """
    if db is None:
        return {"notifications": [], "count": 0}

    user_id = current_user.get("_id")
    try:
        notifs = list(
            db.notifications.find(
                {"user_id": user_id},
                {"_id": 0},
            ).sort("timestamp", -1).limit(50)
        )
    except Exception:
        notifs = []

    return {"notifications": notifs, "count": len(notifs)}
