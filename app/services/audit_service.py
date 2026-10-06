"""
GridMind AI — Audit Logging Service (MongoDB-backed)
=====================================================
Records immutable audit events for all security-sensitive operations.

Action types:
    LOGIN, LOGOUT, FAILED_LOGIN, VIEW_DATA, CREATE_USER, UPDATE_USER,
    DELETE_USER, ACKNOWLEDGE_ALERT, UPDATE_ALERT, ACCESS_DENIED,
    UPDATE_INCIDENT, CHANGE_PASSWORD

NEVER stores passwords, JWT tokens, or other secrets.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)


def log_audit_event(
    db: Optional[Database],
    *,
    action: str,
    username: str,
    role: str,
    ip_address: str,
    resource: str = "",
    user_id: Optional[str] = None,
    details: str = "",
) -> None:
    """
    Insert an audit event into the `audit_logs` MongoDB collection.

    Args:
        db:          Active MongoDB database handle (no-op if None).
        action:      Action type constant (e.g., 'LOGIN', 'ACCESS_DENIED').
        username:    Username performing the action.
        role:        Role of the user (AE, DE, or 'anonymous').
        ip_address:  Client IP address.
        resource:    Resource identifier (e.g., alert_id, endpoint path).
        user_id:     Internal user ID from the users collection.
        details:     Human-readable detail string. NEVER include passwords/tokens.
    """
    if db is None:
        logger.debug(
            "Audit log skipped (no DB): action=%s user=%s", action, username
        )
        return

    entry = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "action": action,
        "resource": resource,
        "ip_address": ip_address,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        db.audit_logs.insert_one(entry)
    except Exception as exc:
        # Audit logging must never crash the application
        logger.error("Failed to write audit log entry: %s", exc)


def get_audit_logs(
    db: Optional[Database],
    limit: int = 100,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    username: Optional[str] = None,
) -> list[dict]:
    """
    Retrieve audit log entries from MongoDB, newest first.

    Args:
        db:       Active MongoDB database handle.
        limit:    Maximum number of entries to return.
        user_id:  Filter by user_id.
        action:   Filter by action type.
        username: Filter by username.

    Returns:
        List of audit log documents (ObjectId converted to str).
    """
    if db is None:
        return []

    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    if username:
        query["username"] = username

    try:
        cursor = (
            db.audit_logs
            .find(query, {"_id": 0})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception as exc:
        logger.error("Failed to retrieve audit logs: %s", exc)
        return []
