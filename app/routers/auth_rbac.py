"""
GridMind AI — RBAC Authentication Router (v2)
=============================================
Accepts BOTH JSON body (old frontend) AND form-encoded (OAuth2/Swagger).
Includes brute-force protection, refresh token rotation, audit logging.

PREFIX: /auth
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from pymongo.database import Database

from app.core.dependencies import get_current_user, get_db_dep
from app.core.security import (
    brute_force_guard,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.services.audit_service import log_audit_event
from app.services.user_service import get_user_by_username_with_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _public_user(user: dict) -> dict:
    """Return safe user dict — never includes password_hash."""
    return {
        "username":    user.get("username"),
        "name":        user.get("name", ""),
        "email":       user.get("email", ""),
        "role":        user.get("role"),
        "role_label":  user.get("role_label", user.get("role", "")),
        "division_id": user.get("division_id"),
        "is_active":   user.get("is_active", True),
        "permissions": user.get("permissions", []),
    }


def _issue_tokens(user: dict, db: Optional[Database], ip: str) -> dict:
    """Create access + refresh tokens, store refresh token in DB, return response dict."""
    token_data = {"sub": user["username"], "role": user["role"]}
    access_token   = create_access_token(token_data)
    refresh_token  = create_refresh_token(token_data)

    # Store hashed refresh token
    if db is not None:
        import hashlib
        from app.core.config import get_settings
        from datetime import timedelta
        settings   = get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        tok_hash   = hashlib.sha256(refresh_token.encode()).hexdigest()
        try:
            db.refresh_tokens.insert_one({
                "token_hash": tok_hash,
                "user_id":    str(user.get("_id", "")),
                "username":   user["username"],
                "is_revoked": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
            })
        except Exception as exc:
            logger.warning("Failed to store refresh token: %s", exc)

    brute_force_guard.record_success(ip)
    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "user":          _public_user(user),
    }


def _reject_login(db, username: str, role: str, ip: str, detail: str, code: int = 401) -> None:
    """Record failed login audit event and raise HTTPException."""
    brute_force_guard.record_failure(ip)
    remaining = brute_force_guard.remaining_attempts(ip)
    log_audit_event(
        db,
        action="FAILED_LOGIN",
        username=username,
        role=role,
        ip_address=ip,
        resource="auth/login",
        details=f"{detail}  ({remaining} attempts before lockout)",
    )
    raise HTTPException(
        status_code=code,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Pydantic schema for JSON body login (used by the existing frontend)
# ---------------------------------------------------------------------------
class LoginJSON(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


# ---------------------------------------------------------------------------
# LOGIN  —  accepts both form-encoded (Swagger/OAuth2) and JSON body
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    summary="Login — accepts form-encoded OR JSON body",
    description=(
        "**Form-encoded** (Swagger / OAuth2):\n"
        "`username=de001&password=GridDE@2026!`\n\n"
        "**JSON body** (existing frontend):\n"
        "`{\"username\": \"de001\", \"password\": \"GridDE@2026!\"}`\n\n"
        "Brute-force protection: 5 failures → locked for 15 minutes."
    ),
)
async def login(
    request: Request,
    db: Optional[Database] = Depends(get_db_dep),
):
    """
    Universal login endpoint — detects Content-Type and parses accordingly.
    Returns: access_token, refresh_token, token_type, user.
    """
    ip = _get_ip(request)

    # --- Brute-force check ---
    if brute_force_guard.is_locked(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Your IP is temporarily blocked. Try again in 15 minutes.",
            headers={"Retry-After": "900"},
        )

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )

    # --- Parse credentials from EITHER form or JSON ---
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            body = await request.json()
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
        else:
            form = await request.form()
            username = str(form.get("username", "")).strip().lower()
            password = str(form.get("password", ""))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse login credentials.",
        )

    if not username or not password:
        _reject_login(db, username or "?", "unknown", ip, "Username and password are required.")

    # --- Lookup user ---
    user = get_user_by_username_with_hash(db, username)

    if user is None:
        _reject_login(db, username, "unknown", ip, "Invalid username or password.")

    if not verify_password(password, user.get("password_hash", "")):
        _reject_login(db, username, user.get("role", "unknown"), ip, "Invalid username or password.")

    if not user.get("is_active", True):
        _reject_login(
            db, username, user.get("role", "unknown"), ip,
            "Account is deactivated. Contact your Divisional Engineer.",
            code=403,
        )

    # --- Issue tokens ---
    log_audit_event(
        db,
        action="LOGIN",
        username=user["username"],
        role=user["role"],
        ip_address=ip,
        resource="auth/login",
        user_id=str(user.get("_id", "")),
        details="Successful authentication.",
    )

    return _issue_tokens(user, db, ip)


# ---------------------------------------------------------------------------
# REFRESH TOKEN
# ---------------------------------------------------------------------------

@router.post("/refresh", summary="Refresh access token")
async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    db: Optional[Database] = Depends(get_db_dep),
):
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    token_payload = decode_refresh_token(payload.refresh_token)
    if token_payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    import hashlib
    tok_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    stored   = db.refresh_tokens.find_one({"token_hash": tok_hash})
    if not stored or stored.get("is_revoked", False):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    user = get_user_by_username_with_hash(db, token_payload.get("sub", ""))
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="User account not found or deactivated.")

    new_access = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": new_access, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------

@router.post("/logout", summary="Logout and invalidate refresh token")
async def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Optional[Database] = Depends(get_db_dep),
):
    ip = _get_ip(request)

    if db is not None and payload.refresh_token:
        try:
            import hashlib
            tok_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
            db.refresh_tokens.update_one(
                {"token_hash": tok_hash, "username": current_user["username"]},
                {"$set": {"is_revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception as exc:
            logger.warning("Refresh token revoke failed: %s", exc)

    log_audit_event(
        db,
        action="LOGOUT",
        username=current_user["username"],
        role=current_user["role"],
        ip_address=ip,
        resource="auth/logout",
        user_id=current_user.get("_id"),
    )
    return {"status": "success", "message": "Logged out successfully."}


# ---------------------------------------------------------------------------
# ME — current user profile
# ---------------------------------------------------------------------------

@router.get("/me", summary="Current user profile")
async def get_me(current_user: dict = Depends(get_current_user)):
    return _public_user(current_user)


# ---------------------------------------------------------------------------
# AUDIT-LOGS — kept for backward compat with old frontend Security tab
# ---------------------------------------------------------------------------

@router.get("/audit-logs", summary="Security audit logs (backward compat)")
async def get_audit_logs_compat(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: Optional[Database] = Depends(get_db_dep),
):
    """Backward-compatible audit log endpoint for the legacy frontend Security tab."""
    from app.services.audit_service import get_audit_logs
    logs = get_audit_logs(db, limit=limit)
    return {
        "count": len(logs),
        "logs": logs,
        "active_security_admins": 0,
        "system_status": "MONITORING_ACTIVE",
    }


# ---------------------------------------------------------------------------
# AUDIT-EVENT — kept for backward compat with old frontend
# ---------------------------------------------------------------------------

class SecurityEventRequest(BaseModel):
    event_type: str
    details: str
    status: str = "INFO"


@router.post("/audit-event", summary="Record client audit event (backward compat)")
async def record_audit_event(
    event: SecurityEventRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Optional[Database] = Depends(get_db_dep),
):
    ip = _get_ip(request)
    log_audit_event(
        db,
        action=event.event_type,
        username=current_user["username"],
        role=current_user["role"],
        ip_address=ip,
        resource="client_event",
        user_id=current_user.get("_id"),
        details=event.details,
    )
    return {"status": "recorded"}
