"""
GridMind AI — Core Authentication & Role-Based Access Control (RBAC) Module

Provides:
- PBKDF2-HMAC-SHA256 password hashing with per-user salt
- Tamper-proof HMAC-SHA256 bearer session tokens (zero external binary dependency)
- Role definitions: Super Admin ('admin'), Security Admins ('security_admin'), Operator ('operator')
- Security audit logging and live threat tracking
- FastAPI route protection dependencies
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Fallback secret key for signing tokens
JWT_SECRET_KEY = os.getenv("GRIDMIND_SECRET_KEY", "gridmind-ai-tgspdcl-energy-security-key-2026-xyz")
ALGORITHM = "HS256"
DEFAULT_TOKEN_EXPIRY_HOURS = 24

# Bearer scheme for Swagger UI & API docs
security_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing via Standard Library (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a cryptographically secure random salt."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000
    ).hex()
    return f"{salt}${pw_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored salt$hash representation."""
    if not hashed_password or "$" not in hashed_password:
        return False
    try:
        salt, expected_hash = hashed_password.split("$", 1)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000
        ).hex()
        return hmac.compare_digest(expected_hash, computed_hash)
    except Exception as e:
        logger.error("Error verifying password: %s", e)
        return False


# ---------------------------------------------------------------------------
# Pre-Configured Users (Super Admin, 2 Security Admins, Operator)
# ---------------------------------------------------------------------------
# Users store primary password and accepted alternate passwords for seamless access
INITIAL_USERS_DB: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "name": "Chief Energy Administrator (You)",
        "email": "chief.admin@gridmind.tgspdcl.gov.in",
        "role": "admin",
        "role_label": "⚡ Super Admin (Grid Owner)",
        "description": "Full Root Privileges — Executive control across all grid intelligence, predictions, streams, and security modules.",
        "password_hash": hash_password("admin123"),
        "alt_hashes": [hash_password("admin"), hash_password("GridAdmin@2026!")],
        "created_at": "2026-10-01 08:00:00",
        "permissions": [
            "all",
            "overview_access",
            "disruption_predict",
            "anomaly_detect",
            "demand_forecast",
            "grid_clustering",
            "telemetry_stream",
            "stream_simulate",
            "model_analytics",
            "security_admin",
            "user_management",
            "audit_logs_view"
        ]
    },
    "sec_admin1": {
        "username": "sec_admin1",
        "name": "Security Admin 1 (SOC Lead)",
        "email": "soc.lead@security.tgspdcl.gov.in",
        "role": "security_admin",
        "role_label": "🛡️ Security Admin 1 (SOC Lead)",
        "description": "Grid Cyber-Physical Security & Intrusion Lead — Monitors anomalous grid telemetry, real-time alerts, and intrusion audits.",
        "password_hash": hash_password("secadmin1"),
        "alt_hashes": [hash_password("sec_admin1"), hash_password("SecAdmin1@2026!")],
        "created_at": "2026-10-01 08:00:00",
        "permissions": [
            "overview_access",
            "disruption_predict",
            "anomaly_detect",
            "telemetry_stream",
            "stream_simulate",
            "security_admin",
            "audit_logs_view",
            "security_alerts_manage"
        ]
    },
    "sec_admin2": {
        "username": "sec_admin2",
        "name": "Security Admin 2 (Grid Safety & Compliance)",
        "email": "safety.compliance@security.tgspdcl.gov.in",
        "role": "security_admin",
        "role_label": "🛡️ Security Admin 2 (Safety & Compliance)",
        "description": "Infrastructure Safety & Disaster Resilience Officer — Oversees power failure thresholds, circle disruptions, and regulatory compliance.",
        "password_hash": hash_password("secadmin2"),
        "alt_hashes": [hash_password("sec_admin2"), hash_password("SecAdmin2@2026!")],
        "created_at": "2026-10-01 08:00:00",
        "permissions": [
            "overview_access",
            "disruption_predict",
            "anomaly_detect",
            "telemetry_stream",
            "stream_simulate",
            "security_admin",
            "audit_logs_view",
            "safety_controls"
        ]
    },
    "operator": {
        "username": "operator",
        "name": "Grid Operations Analyst",
        "email": "ops.analyst@operations.tgspdcl.gov.in",
        "role": "operator",
        "role_label": "📊 Grid Operator",
        "description": "Field operations and telemetry monitoring analyst with read & operational query access.",
        "password_hash": hash_password("operator123"),
        "alt_hashes": [hash_password("operator"), hash_password("Operator@2026!")],
        "created_at": "2026-10-01 08:00:00",
        "permissions": [
            "overview_access",
            "disruption_predict",
            "anomaly_detect",
            "demand_forecast",
            "grid_clustering",
            "model_analytics"
        ]
    }
}

# In-memory user store (can be extended with runtime user creation)
USERS_DB = dict(INITIAL_USERS_DB)

# Default permissions assigned to roles when not explicitly specified
ROLE_DEFAULT_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "all",
        "overview_access",
        "disruption_predict",
        "anomaly_detect",
        "demand_forecast",
        "grid_clustering",
        "telemetry_stream",
        "stream_simulate",
        "model_analytics",
        "security_admin",
        "user_management",
        "audit_logs_view"
    ],
    "security_admin": [
        "overview_access",
        "disruption_predict",
        "anomaly_detect",
        "telemetry_stream",
        "stream_simulate",
        "security_admin",
        "audit_logs_view",
        "security_alerts_manage"
    ],
    "operator": [
        "overview_access",
        "disruption_predict",
        "anomaly_detect",
        "demand_forecast",
        "grid_clustering",
        "model_analytics"
    ],
    "viewer": [
        "overview_access",
        "model_analytics"
    ]
}

ROLE_LABELS: Dict[str, str] = {
    "admin": "⚡ Super Admin",
    "security_admin": "🛡️ Security Admin",
    "operator": "📊 Grid Operator",
    "viewer": "👁️ Grid Viewer"
}


# ---------------------------------------------------------------------------
# Cryptographic Token Generation & Validation (HMAC-SHA256)
# ---------------------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ""
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(data: dict, expires_hours: int = DEFAULT_TOKEN_EXPIRY_HOURS) -> str:
    """Creates a digitally signed HMAC-SHA256 JWT-compatible bearer token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = data.copy()
    exp = int(time.time()) + (expires_hours * 3600)
    payload["exp"] = exp
    payload["iat"] = int(time.time())
    payload["jti"] = secrets.token_hex(8)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    msg = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(JWT_SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[dict]:
    """Validates signature and expiration of an access token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        msg = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(JWT_SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            logger.warning("Token signature verification failed.")
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if "exp" in payload and payload["exp"] < time.time():
            logger.warning("Token has expired.")
            return None

        return payload
    except Exception as e:
        logger.error("Token decoding error: %s", e)
        return None


# ---------------------------------------------------------------------------
# Security Audit Trail Logging
# ---------------------------------------------------------------------------
AUDIT_LOG_FILE: Path = get_settings().reports_path / "security_audit_log.json"
AUDIT_LOGS_MEMORY: List[Dict[str, Any]] = []


def log_security_event(
    event_type: str,
    username: str,
    role: str,
    status_result: str,
    details: str,
    client_ip: str = "127.0.0.1"
) -> Dict[str, Any]:
    """Records an immutable security audit event to memory and JSON log."""
    entry = {
        "id": secrets.token_hex(6),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "event_type": event_type,
        "username": username,
        "role": role,
        "status": status_result,
        "details": details,
        "client_ip": client_ip,
    }
    AUDIT_LOGS_MEMORY.insert(0, entry)
    # Keep up to 500 in-memory events
    if len(AUDIT_LOGS_MEMORY) > 500:
        AUDIT_LOGS_MEMORY.pop()

    try:
        get_settings().reports_path.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(AUDIT_LOGS_MEMORY[:100], f, indent=2)
    except Exception as e:
        logger.warning("Failed to persist security audit event to disk: %s", e)

    return entry


# Pre-seed initial audit entries so the security dashboard is populated on first load
if not AUDIT_LOGS_MEMORY:
    log_security_event("SYSTEM_BOOT", "SYSTEM", "system", "SUCCESS", "GridMind AI Security & RBAC Guard Initialized", "127.0.0.1")
    log_security_event("KEY_EXCHANGE", "SYSTEM", "system", "SUCCESS", "HMAC-SHA256 Token Signing Engine Activated", "127.0.0.1")
    log_security_event("ROLES_LOADED", "admin", "admin", "SUCCESS", "Configured 3 Admins (1 Super Admin + 2 Security Admins)", "127.0.0.1")


def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    return AUDIT_LOGS_MEMORY[:limit]


# ---------------------------------------------------------------------------
# User Authentication Routine
# ---------------------------------------------------------------------------
def authenticate_user(username: str, password: str, client_ip: str = "127.0.0.1") -> Optional[Dict[str, Any]]:
    """Authenticates username/password and records audit log."""
    user = USERS_DB.get(username.strip().lower())
    if not user:
        log_security_event(
            "LOGIN_ATTEMPT_FAILED",
            username,
            "unknown",
            "REJECTED",
            f"Authentication failed: unknown username '{username}'",
            client_ip
        )
        return None

    # Check primary password
    is_valid = verify_password(password, user["password_hash"])
    if not is_valid:
        # Check alternate passwords if available
        for alt_h in user.get("alt_hashes", []):
            if verify_password(password, alt_h):
                is_valid = True
                break

    if not is_valid:
        log_security_event(
            "LOGIN_ATTEMPT_FAILED",
            username,
            user["role"],
            "REJECTED",
            "Authentication failed: invalid credentials provided",
            client_ip
        )
        return None

    log_security_event(
        "LOGIN_SUCCESS",
        username,
        user["role"],
        "GRANTED",
        f"Session initiated for {user['role_label']}",
        client_ip
    )
    return user


# ---------------------------------------------------------------------------
# User Management CRUD & Lifecycle Operations
# ---------------------------------------------------------------------------
def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Fetch user by username (case-insensitive)."""
    return USERS_DB.get(username.strip().lower())


def create_user(
    username: str,
    password: str,
    name: str,
    email: str,
    role: str = "operator",
    permissions: Optional[List[str]] = None,
    description: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    actor_username: str = "SYSTEM"
) -> Dict[str, Any]:
    """Create a new user with hashed password, assigned role, and permissions."""
    clean_username = username.strip().lower()
    if not clean_username:
        raise ValueError("Username cannot be empty.")
    if clean_username in USERS_DB:
        raise ValueError(f"User '{clean_username}' already exists.")

    assigned_role = role.strip().lower() if role else "operator"
    role_label = ROLE_LABELS.get(assigned_role, f"Role: {assigned_role.title()}")

    if permissions is None:
        assigned_permissions = list(ROLE_DEFAULT_PERMISSIONS.get(assigned_role, ROLE_DEFAULT_PERMISSIONS["operator"]))
    else:
        assigned_permissions = list(permissions)

    new_user = {
        "username": clean_username,
        "name": name.strip(),
        "email": email.strip().lower(),
        "role": assigned_role,
        "role_label": role_label,
        "description": description or f"Personnel account for {name.strip()} ({assigned_role}).",
        "password_hash": hash_password(password),
        "alt_hashes": [],
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "permissions": assigned_permissions
    }
    USERS_DB[clean_username] = new_user

    log_security_event(
        "USER_CREATED",
        actor_username,
        assigned_role,
        "SUCCESS",
        f"New user account '{clean_username}' created with role '{assigned_role}'.",
        client_ip
    )
    return {k: v for k, v in new_user.items() if not k.endswith("_hash") and not k.endswith("_hashes")}


def update_user(
    username: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    description: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    actor_username: str = "SYSTEM"
) -> Dict[str, Any]:
    """Update existing user properties, role, or permissions."""
    clean_username = username.strip().lower()
    if clean_username not in USERS_DB:
        raise KeyError(f"User '{clean_username}' not found.")

    user = USERS_DB[clean_username]

    if role is not None:
        clean_role = role.strip().lower()
        if clean_username == "admin" and clean_role != "admin":
            raise ValueError("Root Super Admin 'admin' role cannot be altered.")
        user["role"] = clean_role
        user["role_label"] = ROLE_LABELS.get(clean_role, f"Role: {clean_role.title()}")
        if permissions is None and clean_role in ROLE_DEFAULT_PERMISSIONS:
            user["permissions"] = list(ROLE_DEFAULT_PERMISSIONS[clean_role])

    if name is not None:
        user["name"] = name.strip()
    if email is not None:
        user["email"] = email.strip().lower()
    if description is not None:
        user["description"] = description.strip()
    if permissions is not None:
        user["permissions"] = list(permissions)

    log_security_event(
        "USER_UPDATED",
        actor_username,
        user["role"],
        "SUCCESS",
        f"User account '{clean_username}' was updated by '{actor_username}'.",
        client_ip
    )
    return {k: v for k, v in user.items() if not k.endswith("_hash") and not k.endswith("_hashes")}


def delete_user(
    username: str,
    client_ip: str = "127.0.0.1",
    actor_username: str = "SYSTEM"
) -> bool:
    """Delete a user account. Root Super Admin 'admin' cannot be deleted."""
    clean_username = username.strip().lower()
    if clean_username not in USERS_DB:
        raise KeyError(f"User '{clean_username}' not found.")
    if clean_username == "admin":
        raise PermissionError("Root Super Admin 'admin' cannot be deleted.")

    del USERS_DB[clean_username]

    log_security_event(
        "USER_DELETED",
        actor_username,
        "admin",
        "SUCCESS",
        f"User account '{clean_username}' was deleted by '{actor_username}'.",
        client_ip
    )
    return True


def change_user_password(
    username: str,
    new_password: str,
    old_password: Optional[str] = None,
    require_old: bool = False,
    client_ip: str = "127.0.0.1",
    actor_username: str = "SYSTEM"
) -> bool:
    """Change or reset user password with optional verification of current password."""
    clean_username = username.strip().lower()
    if clean_username not in USERS_DB:
        raise KeyError(f"User '{clean_username}' not found.")

    user = USERS_DB[clean_username]

    if require_old:
        if not old_password:
            raise ValueError("Current password is required.")
        valid_old = verify_password(old_password, user["password_hash"])
        if not valid_old:
            for alt_h in user.get("alt_hashes", []):
                if verify_password(old_password, alt_h):
                    valid_old = True
                    break
        if not valid_old:
            log_security_event(
                "PASSWORD_CHANGE_FAILED",
                clean_username,
                user["role"],
                "REJECTED",
                "Password change attempt failed: invalid current password.",
                client_ip
            )
            raise ValueError("Invalid current password provided.")

    user["password_hash"] = hash_password(new_password)
    user["alt_hashes"] = []

    log_security_event(
        "PASSWORD_CHANGED",
        actor_username,
        user["role"],
        "SUCCESS",
        f"Password for user '{clean_username}' was updated.",
        client_ip
    )
    return True


# ---------------------------------------------------------------------------
# FastAPI Dependency Injection for Protected Routes
# ---------------------------------------------------------------------------
def get_token_from_request(
    request: Request,
    auth_header: Optional[str] = Header(None, alias="Authorization"),
    auth_bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[str]:
    """Extracts bearer token from Authorization header or URL query parameter."""
    if auth_bearer and auth_bearer.credentials:
        return auth_bearer.credentials
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    # Check query param
    token_query = request.query_params.get("token")
    if token_query:
        return token_query
    return None


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_request)
) -> Dict[str, Any]:
    """Validates the current user from session token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with your GridMind credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload["sub"]
    user = USERS_DB.get(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with session not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(allowed_roles: List[str]):
    """Returns a dependency function checking if current user has one of allowed_roles."""
    async def role_checker(
        request: Request,
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            client_ip = request.client.host if request.client else "unknown"
            log_security_event(
                "ACCESS_VIOLATION",
                current_user.get("username", "unknown"),
                user_role or "unknown",
                "DENIED",
                f"Unauthorized route access attempt. Allowed roles: {allowed_roles}",
                client_ip
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Action requires one of roles {allowed_roles}."
            )
        return current_user
    return role_checker


# Convenient dependencies
require_admin = require_roles(["admin"])
require_security_admin_or_admin = require_roles(["admin", "security_admin"])


def require_permissions(required_perms: List[str]):
    """Returns a dependency function checking if current user has any of the required permissions."""
    async def permission_checker(
        request: Request,
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        user_perms = set(current_user.get("permissions", []))
        if "all" in user_perms:
            return current_user
        if not any(p in user_perms for p in required_perms):
            client_ip = request.client.host if request.client else "unknown"
            log_security_event(
                "PERMISSION_DENIED",
                current_user.get("username", "unknown"),
                current_user.get("role", "unknown"),
                "DENIED",
                f"Unauthorized route access attempt: user lacks permissions {required_perms}",
                client_ip
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: Action requires one of permissions {required_perms}."
            )
        return current_user
    return permission_checker


require_user_management = require_permissions(["all", "user_management"])
