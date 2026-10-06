"""
GridMind AI — User Service (MongoDB CRUD)
==========================================
All user operations use PyMongo (synchronous).
Passwords are NEVER returned in any response.
Mass assignment is prevented by explicit field whitelisting.
"""
from __future__ import annotations

import logging
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from app.core.security import hash_password

logger = logging.getLogger(__name__)

# Fields that are safe to expose in responses (never include password_hash)
_SAFE_PROJECTION = {"password_hash": 0}

# Fields that a DE can update for AE users (mass assignment prevention)
_UPDATABLE_FIELDS = {"name", "email", "is_active", "division_id"}

# A DE cannot assign or escalate to DE role
_AE_ONLY_ROLES = {"AE"}


def _sanitize(user: Optional[dict]) -> Optional[dict]:
    """Convert ObjectId to str and remove password_hash from user dict."""
    if user is None:
        return None
    doc = dict(user)
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    doc.pop("password_hash", None)
    return doc


def get_user_by_username(db: Database, username: str) -> Optional[dict]:
    """
    Fetch a user document by username (case-insensitive).
    Returns sanitized document without password_hash, or None.
    """
    user = db.users.find_one({"username": username.strip().lower()}, _SAFE_PROJECTION)
    return _sanitize(user)


def get_user_by_username_with_hash(db: Database, username: str) -> Optional[dict]:
    """
    Fetch a user document including password_hash.
    Use ONLY for authentication — never return this to API callers.
    """
    user = db.users.find_one({"username": username.strip().lower()})
    if user and "_id" in user and isinstance(user["_id"], ObjectId):
        user["_id"] = str(user["_id"])
    return user


def get_user_by_id(db: Database, user_id: str) -> Optional[dict]:
    """Fetch a user document by _id string. Returns sanitized document."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    user = db.users.find_one({"_id": oid}, _SAFE_PROJECTION)
    return _sanitize(user)


def create_user(db: Database, user_data: dict, actor_role: str = "DE") -> dict:
    """
    Create a new user in the `users` collection.

    Only DE can create users, and only AE-role users (no privilege escalation).

    Args:
        db:         MongoDB database.
        user_data:  Dict with: username, password, email, name, role, division_id.
        actor_role: Role of the creating user (used for validation).

    Returns:
        Sanitized new user document.

    Raises:
        ValueError: If username/email already exists, or role escalation attempted.
    """
    username = user_data["username"].strip().lower()
    email = user_data.get("email", "").strip().lower()
    role = user_data.get("role", "AE").upper()

    # Prevent privilege escalation: DE can only create AE users
    if role not in _AE_ONLY_ROLES:
        raise ValueError(
            f"Cannot create user with role '{role}'. "
            "Divisional Engineers may only create Assistant Engineer (AE) accounts."
        )

    if db.users.find_one({"username": username}):
        raise ValueError(f"Username '{username}' is already taken.")
    if email and db.users.find_one({"email": email}):
        raise ValueError(f"Email '{email}' is already registered.")

    password = user_data.get("password", "")
    if not password:
        raise ValueError("Password is required.")

    doc = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "name": user_data.get("name", "").strip(),
        "division_id": user_data.get("division_id"),
        "is_active": user_data.get("is_active", True),
    }

    from datetime import datetime, timezone
    doc["created_at"] = datetime.now(timezone.utc).isoformat()

    result = db.users.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc.pop("password_hash", None)
    return doc


def update_user(
    db: Database,
    user_id: str,
    updates: dict,
    actor_username: str = "system",
) -> Optional[dict]:
    """
    Update allowed fields for a user.

    Whitelisted updatable fields: name, email, is_active, division_id.
    Role cannot be changed via this function (prevents privilege escalation).

    Args:
        db:             MongoDB database.
        user_id:        _id of user to update.
        updates:        Dict of field→value pairs to apply.
        actor_username: Username of the person making the update (for logging).

    Returns:
        Updated sanitized user document, or None if not found.
    """
    # Whitelist — strip any attempt to set role, password_hash, username
    safe_updates = {k: v for k, v in updates.items() if k in _UPDATABLE_FIELDS}
    if not safe_updates:
        raise ValueError("No valid fields to update.")

    try:
        oid = ObjectId(user_id)
    except Exception:
        return None

    db.users.update_one({"_id": oid}, {"$set": safe_updates})
    user = db.users.find_one({"_id": oid}, _SAFE_PROJECTION)
    return _sanitize(user)


def list_users(
    db: Database,
    role: Optional[str] = None,
    division_id: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> list[dict]:
    """
    List users with optional filters.

    Args:
        db:          MongoDB database.
        role:        Filter by role (e.g., 'AE').
        division_id: Filter by division.
        is_active:   Filter by active status.

    Returns:
        List of sanitized user documents.
    """
    query: dict = {}
    if role:
        query["role"] = role.upper()
    if division_id:
        query["division_id"] = division_id
    if is_active is not None:
        query["is_active"] = is_active

    users = db.users.find(query, _SAFE_PROJECTION)
    return [_sanitize(u) for u in users if u]


def deactivate_user(db: Database, user_id: str) -> bool:
    """
    Deactivate (soft-delete) a user by setting is_active=False.

    Returns True if a document was updated, False otherwise.
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        return False
    result = db.users.update_one({"_id": oid}, {"$set": {"is_active": False}})
    return result.modified_count > 0


def change_password(
    db: Database,
    user_id: str,
    new_password: str,
    old_password: Optional[str] = None,
    require_old: bool = True,
) -> bool:
    """
    Change a user's password.

    Args:
        db:           MongoDB database.
        user_id:      _id of the user.
        new_password: New plain-text password (will be hashed).
        old_password: Current password (required if require_old=True).
        require_old:  Whether to verify old password before changing.

    Returns:
        True on success.

    Raises:
        ValueError: If old password is wrong or user not found.
    """
    from app.core.security import verify_password as _verify

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise ValueError("Invalid user_id format.")

    user = db.users.find_one({"_id": oid})
    if not user:
        raise ValueError("User not found.")

    if require_old:
        if not old_password:
            raise ValueError("Current password is required.")
        if not _verify(old_password, user.get("password_hash", "")):
            raise ValueError("Current password is incorrect.")

    new_hash = hash_password(new_password)
    db.users.update_one({"_id": oid}, {"$set": {"password_hash": new_hash}})
    return True
