"""
GridMind AI — Authentication & Role-Based Access Control Router

Exposes REST endpoints for:
- User login / session issuance
- Session verification & user profile (/me)
- Security audit logs retrieval (Admin & Security Admins only)
- User roster and RBAC permission matrix
- Security event reporting
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import (
    AUDIT_LOGS_MEMORY,
    USERS_DB,
    authenticate_user,
    change_user_password,
    create_access_token,
    create_user,
    delete_user,
    get_audit_logs,
    get_current_user,
    get_user,
    hash_password,
    log_security_event,
    require_admin,
    require_permissions,
    require_security_admin_or_admin,
    require_user_management,
    update_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., example="admin")
    password: str = Field(..., example="admin123")


class UserProfileResponse(BaseModel):
    username: str
    name: str
    email: str
    role: str
    role_label: str
    description: str
    permissions: List[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class SecurityEventRequest(BaseModel):
    event_type: str
    details: str
    status: str = "INFO"


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, example="operator_live")
    password: str = Field(..., min_length=6, max_length=128, example="GridOperator@2026")
    name: str = Field(..., min_length=2, max_length=100, example="Field Operations Engineer")
    email: str = Field(..., example="engineer@tgspdcl.gov.in")
    role: str = Field("operator", example="operator")
    description: Optional[str] = Field(None, example="Substation telemetry monitoring engineer")
    permissions: Optional[List[str]] = Field(None, example=["overview_access", "disruption_predict"])


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class UserDetailResponse(BaseModel):
    username: str
    name: str
    email: str
    role: str
    role_label: str
    description: str
    permissions: List[str]
    created_at: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128, description="New password for user")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, request: Request):
    """Authenticate user with username and password, return JWT-compatible bearer token."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user = authenticate_user(credentials.username, credentials.password, client_ip=client_ip)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password. Please verify credentials."
        )

    token = create_access_token({
        "sub": user["username"],
        "role": user["role"],
        "name": user["name"]
    })

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            username=user["username"],
            name=user["name"],
            email=user["email"],
            role=user["role"],
            role_label=user["role_label"],
            description=user["description"],
            permissions=user["permissions"]
        )
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve details and RBAC permissions for the currently authenticated user."""
    return UserProfileResponse(
        username=current_user["username"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user["role"],
        role_label=current_user["role_label"],
        description=current_user["description"],
        permissions=current_user["permissions"]
    )


@router.post("/logout")
async def logout(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Log out current user and write audit trail entry."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    log_security_event(
        "USER_LOGOUT",
        current_user["username"],
        current_user["role"],
        "SUCCESS",
        f"User {current_user['name']} logged out safely.",
        client_ip
    )
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/users")
async def list_authorized_users(current_user: Dict[str, Any] = Depends(require_security_admin_or_admin)):
    """List all authorized users, roles, and administrative statuses (Security Admins & Admin only)."""
    users_list = []
    for u in USERS_DB.values():
        users_list.append({
            "username": u["username"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "role_label": u["role_label"],
            "description": u["description"],
            "permissions": u.get("permissions", []),
            "permissions_count": len(u.get("permissions", [])),
            "created_at": u.get("created_at", "2026-10-01 08:00:00")
        })
    return {"total": len(users_list), "users": users_list}


@router.post("/users", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: CreateUserRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user_management)
):
    """Create a new user account with assigned role and permissions (Admin only)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        new_user = create_user(
            username=user_data.username,
            password=user_data.password,
            name=user_data.name,
            email=user_data.email,
            role=user_data.role,
            permissions=user_data.permissions,
            description=user_data.description,
            client_ip=client_ip,
            actor_username=current_user["username"]
        )
        return UserDetailResponse(
            username=new_user["username"],
            name=new_user["name"],
            email=new_user["email"],
            role=new_user["role"],
            role_label=new_user["role_label"],
            description=new_user["description"],
            permissions=new_user["permissions"],
            created_at=new_user["created_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users/{username}", response_model=UserDetailResponse)
async def get_user_profile(
    username: str,
    current_user: Dict[str, Any] = Depends(require_security_admin_or_admin)
):
    """Fetch profile and RBAC permissions of a specific user (Security Admins & Admin only)."""
    user = get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{username}' not found.")
    return UserDetailResponse(
        username=user["username"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        role_label=user["role_label"],
        description=user["description"],
        permissions=user.get("permissions", []),
        created_at=user.get("created_at", "2026-10-01 08:00:00")
    )


@router.put("/users/{username}", response_model=UserDetailResponse)
async def update_existing_user(
    username: str,
    updates: UpdateUserRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user_management)
):
    """Update profile details, role, or permissions of an existing user (Admin only)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        updated = update_user(
            username=username,
            name=updates.name,
            email=updates.email,
            role=updates.role,
            permissions=updates.permissions,
            description=updates.description,
            client_ip=client_ip,
            actor_username=current_user["username"]
        )
        return UserDetailResponse(
            username=updated["username"],
            name=updated["name"],
            email=updated["email"],
            role=updated["role"],
            role_label=updated["role_label"],
            description=updated["description"],
            permissions=updated["permissions"],
            created_at=updated.get("created_at", "2026-10-01 08:00:00")
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{username}")
async def delete_existing_user(
    username: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user_management)
):
    """Delete a user account. Root Super Admin cannot be deleted (Admin only)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        delete_user(username=username, client_ip=client_ip, actor_username=current_user["username"])
        return {"status": "success", "message": f"User account '{username}' was successfully deleted."}
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/users/{username}/reset-password")
async def admin_reset_user_password(
    username: str,
    payload: AdminResetPasswordRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_user_management)
):
    """Reset password for any user account (Admin only)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        change_user_password(
            username=username,
            new_password=payload.new_password,
            require_old=False,
            client_ip=client_ip,
            actor_username=current_user["username"]
        )
        return {"status": "success", "message": f"Password for '{username}' was reset successfully."}
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password")
async def change_own_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Allows currently logged-in user to change their own password."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    try:
        change_user_password(
            username=current_user["username"],
            new_password=payload.new_password,
            old_password=payload.old_password,
            require_old=True,
            client_ip=client_ip,
            actor_username=current_user["username"]
        )
        return {"status": "success", "message": "Your password has been changed successfully."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/audit-logs")
async def get_security_audit_logs(
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_security_admin_or_admin)
):
    """Retrieve live security audit logs (Admin and Security Admins only)."""
    logs = get_audit_logs(limit=limit)
    return {
        "count": len(logs),
        "logs": logs,
        "active_security_admins": 2,
        "system_status": "MONITORING_ACTIVE"
    }


@router.post("/audit-event")
async def record_client_audit_event(
    event: SecurityEventRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Allows authenticated frontend clients to report security-relevant events."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    entry = log_security_event(
        event.event_type,
        current_user["username"],
        current_user["role"],
        event.status,
        event.details,
        client_ip
    )
    return {"status": "recorded", "event": entry}


@router.get("/matrix")
async def get_rbac_matrix():
    """Returns the RBAC permissions matrix defining capabilities per role."""
    return {
        "roles": [
            {
                "key": "admin",
                "title": "Super Admin (You)",
                "description": "Full administrative control, root access, user configuration & model pipelines",
                "badge": "⚡ Super Admin",
                "badge_color": "#06b6d4",
                "access": {
                    "Executive Overview": "Full Access",
                    "Disruption Prediction": "Full Access + Threshold Tuning",
                    "Smart Meter Anomaly Detection": "Full Access",
                    "Energy Demand Forecasting": "Full Access",
                    "Grid Circles & Clusters": "Full Access",
                    "Live Telemetry Stream Simulation": "Execute & Configure",
                    "Model Analytics & Reports": "Full Access + Re-evaluation",
                    "Security & Audit Console": "Full Control + User Management"
                }
            },
            {
                "key": "security_admin",
                "title": "Security Admin (2 Dedicated Officers)",
                "description": "Security Operations Center (SOC) & Grid Safety Compliance officers",
                "badge": "🛡️ Security Admin",
                "badge_color": "#ef4444",
                "access": {
                    "Executive Overview": "Full Access",
                    "Disruption Prediction": "Threat Monitoring",
                    "Smart Meter Anomaly Detection": "Anomaly & Intrusion Audit",
                    "Energy Demand Forecasting": "Read Access",
                    "Grid Circles & Clusters": "Safety Review",
                    "Live Telemetry Stream Simulation": "Execute & Audit",
                    "Model Analytics & Reports": "Audit & Review",
                    "Security & Audit Console": "Full Audit Trail & Intrusion Inspection"
                }
            },
            {
                "key": "operator",
                "title": "Grid Operations Analyst",
                "description": "Daily monitoring of circles, loads, and telemetry data",
                "badge": "📊 Operator",
                "badge_color": "#10b981",
                "access": {
                    "Executive Overview": "Read Access",
                    "Disruption Prediction": "Prediction Run Only",
                    "Smart Meter Anomaly Detection": "Anomaly Check Only",
                    "Energy Demand Forecasting": "Read & Export",
                    "Grid Circles & Clusters": "Read Access",
                    "Live Telemetry Stream Simulation": "Restricted (Admin Only)",
                    "Model Analytics & Reports": "Read Access",
                    "Security & Audit Console": "No Access"
                }
            }
        ]
    }
