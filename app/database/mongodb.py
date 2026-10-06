"""
GridMind AI — MongoDB Index Setup
===================================
Creates all required collections and indexes on startup.
Safe to call multiple times (idempotent).
"""
from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


def _safe_create_indexes(collection, indexes: list, collection_name: str) -> None:
    """Create indexes, logging errors without crashing."""
    for idx in indexes:
        try:
            collection.create_index(idx.document["key"], **{
                k: v for k, v in idx.document.items()
                if k not in ("key", "v", "ns")
            })
        except OperationFailure as exc:
            logger.warning("Index creation warning on %s: %s", collection_name, exc)
        except Exception as exc:
            logger.error("Index creation failed on %s: %s", collection_name, exc)


def setup_indexes(db: Database) -> None:
    """
    Create all MongoDB indexes required for GridMind AI RBAC.
    Call once during application startup.
    """
    logger.info("Setting up MongoDB indexes...")

    # users collection
    _safe_create_indexes(
        db.users,
        [
            IndexModel([("username", ASCENDING)], name="idx_users_username", unique=True),
            IndexModel([("email", ASCENDING)], name="idx_users_email", unique=True, sparse=True),
            IndexModel([("role", ASCENDING)], name="idx_users_role"),
            IndexModel([("division_id", ASCENDING)], name="idx_users_division_id", sparse=True),
            IndexModel([("is_active", ASCENDING)], name="idx_users_is_active"),
        ],
        "users",
    )

    # divisions collection
    _safe_create_indexes(
        db.divisions,
        [
            IndexModel([("division_id", ASCENDING)], name="idx_divisions_id", unique=True),
            IndexModel([("name", ASCENDING)], name="idx_divisions_name"),
        ],
        "divisions",
    )

    # meters collection
    _safe_create_indexes(
        db.meters,
        [
            IndexModel([("meter_id", ASCENDING)], name="idx_meters_id", unique=True),
            IndexModel([("division_id", ASCENDING)], name="idx_meters_division_id"),
        ],
        "meters",
    )

    # energy_data collection
    _safe_create_indexes(
        db.energy_data,
        [
            IndexModel([("meter_id", ASCENDING)], name="idx_energy_meter_id"),
            IndexModel([("division_id", ASCENDING)], name="idx_energy_division_id"),
            IndexModel(
                [("meter_id", ASCENDING), ("timestamp", DESCENDING)],
                name="idx_energy_meter_timestamp",
            ),
            IndexModel([("timestamp", DESCENDING)], name="idx_energy_timestamp"),
        ],
        "energy_data",
    )

    # predictions collection
    _safe_create_indexes(
        db.predictions,
        [
            IndexModel([("division_id", ASCENDING)], name="idx_predictions_division_id"),
            IndexModel([("timestamp", DESCENDING)], name="idx_predictions_timestamp"),
        ],
        "predictions",
    )

    # anomalies collection
    _safe_create_indexes(
        db.anomalies,
        [
            IndexModel([("division_id", ASCENDING)], name="idx_anomalies_division_id"),
            IndexModel([("meter_id", ASCENDING)], name="idx_anomalies_meter_id"),
            IndexModel(
                [("division_id", ASCENDING), ("detected_at", DESCENDING)],
                name="idx_anomalies_div_detected",
            ),
            IndexModel([("is_resolved", ASCENDING)], name="idx_anomalies_is_resolved"),
        ],
        "anomalies",
    )

    # alerts collection
    _safe_create_indexes(
        db.alerts,
        [
            IndexModel([("division_id", ASCENDING)], name="idx_alerts_division_id"),
            IndexModel([("timestamp", DESCENDING)], name="idx_alerts_timestamp"),
            IndexModel([("severity", ASCENDING)], name="idx_alerts_severity"),
            IndexModel([("is_acknowledged", ASCENDING)], name="idx_alerts_acknowledged"),
        ],
        "alerts",
    )

    # audit_logs collection
    _safe_create_indexes(
        db.audit_logs,
        [
            IndexModel([("user_id", ASCENDING)], name="idx_audit_user_id"),
            IndexModel([("username", ASCENDING)], name="idx_audit_username"),
            IndexModel([("timestamp", DESCENDING)], name="idx_audit_timestamp"),
            IndexModel([("action", ASCENDING)], name="idx_audit_action"),
        ],
        "audit_logs",
    )

    # refresh_tokens collection — TTL index for automatic cleanup
    _safe_create_indexes(
        db.refresh_tokens,
        [
            IndexModel([("token_hash", ASCENDING)], name="idx_refresh_token_hash", unique=True),
            IndexModel([("user_id", ASCENDING)], name="idx_refresh_user_id"),
            IndexModel([("username", ASCENDING)], name="idx_refresh_username"),
            IndexModel([("is_revoked", ASCENDING)], name="idx_refresh_is_revoked"),
            IndexModel(
                [("expires_at", ASCENDING)],
                name="idx_refresh_expires_ttl",
                expireAfterSeconds=0,  # MongoDB removes docs when expires_at passes
            ),
        ],
        "refresh_tokens",
    )

    logger.info("MongoDB indexes setup complete.")
