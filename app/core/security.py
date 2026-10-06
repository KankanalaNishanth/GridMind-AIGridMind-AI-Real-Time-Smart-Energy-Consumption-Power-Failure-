"""
GridMind AI — Core Security Module (RBAC v2)
=============================================
Provides:
- bcrypt password hashing / verification (via passlib)
- JWT access & refresh token creation / decoding (via python-jose)
- OAuth2PasswordBearer scheme
- In-memory brute-force protection (per-IP)
- Password strength validation
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing — bcrypt via passlib
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception as exc:
        logger.warning("Password verification error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Password strength validation
# ---------------------------------------------------------------------------
import re


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid: bool, message: str).
    Rules: min 8 chars, >=1 uppercase, >=1 digit, >=1 special character.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return False, "Password must contain at least one special character."
    return True, "Password is strong."


# ---------------------------------------------------------------------------
# OAuth2 scheme (used in Swagger UI / dependency injection)
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------------------------
# JWT token creation & decoding
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload to embed (must include 'sub' key).
        expires_delta: Custom expiry duration; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    payload = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({
        "iat": now,
        "exp": expire,
        "type": "access",
    })
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a signed JWT refresh token with a longer expiry.

    Args:
        data: Payload dict (must include 'sub').

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    payload = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload.update({
        "iat": now,
        "exp": expire,
        "type": "refresh",
    })
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Returns the payload dict if valid and not expired; None otherwise.
    Never raises — caller should check for None.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        # Ensure it's an access token (not a refresh token used as access)
        if payload.get("type") == "refresh":
            logger.warning("Refresh token supplied where access token expected.")
            return None
        return payload
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT refresh token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError as exc:
        logger.debug("Refresh token decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Brute-force login protection (in-memory, per-IP)
# ---------------------------------------------------------------------------

class _BruteForceEntry:
    __slots__ = ("failures", "window_start", "locked_until")

    def __init__(self):
        self.failures: int = 0
        self.window_start: float = time.monotonic()
        self.locked_until: float = 0.0


class BruteForceProtection:
    """
    Thread-safe in-memory brute-force protection.

    Tracks failed login attempts per IP address. After MAX_ATTEMPTS
    failures within WINDOW_SECONDS, the IP is locked for LOCKOUT_SECONDS.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 600, lockout_seconds: int = 900):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._records: dict[str, _BruteForceEntry] = defaultdict(_BruteForceEntry)
        self._lock = threading.Lock()

    def is_locked(self, ip: str) -> bool:
        """Return True if the IP is currently locked out."""
        with self._lock:
            entry = self._records.get(ip)
            if not entry:
                return False
            if entry.locked_until and time.monotonic() < entry.locked_until:
                return True
            # Lock expired — reset
            if entry.locked_until and time.monotonic() >= entry.locked_until:
                del self._records[ip]
            return False

    def record_failure(self, ip: str) -> bool:
        """
        Record a failed login attempt for ip.
        Returns True if the IP is now locked (threshold just crossed).
        """
        with self._lock:
            entry = self._records[ip]
            now = time.monotonic()
            # Reset window if it has elapsed
            if now - entry.window_start > self._window:
                entry.failures = 0
                entry.window_start = now
            entry.failures += 1
            if entry.failures >= self._max_attempts:
                entry.locked_until = now + self._lockout
                logger.warning(
                    "Brute-force lockout activated for IP %s after %d failures.",
                    ip,
                    entry.failures,
                )
                return True
            return False

    def record_success(self, ip: str) -> None:
        """Clear the failure record for ip on successful login."""
        with self._lock:
            self._records.pop(ip, None)

    def remaining_attempts(self, ip: str) -> int:
        """Return how many attempts remain before lockout."""
        with self._lock:
            entry = self._records.get(ip)
            if not entry:
                return self._max_attempts
            return max(0, self._max_attempts - entry.failures)


# Singleton instance used across the application
brute_force_guard = BruteForceProtection(
    max_attempts=get_settings().BRUTE_FORCE_MAX_ATTEMPTS,
    window_seconds=get_settings().BRUTE_FORCE_WINDOW_SECONDS,
)
