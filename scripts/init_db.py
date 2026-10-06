#!/usr/bin/env python
"""
scripts/init_db.py
~~~~~~~~~~~~~~~~~~
Initialize the GridMind AI MongoDB database.

This script is *idempotent* — it is safe to run multiple times.

What it does
------------
  1. Creates every required collection if it does not already exist.
  2. Creates every index (unique, compound, TTL, text, partial) if it does
     not already exist.  MongoDB's ``create_index`` is a no-op when the same
     index already exists, so this will never destroy data.

Usage
-----
  python scripts/init_db.py
  MONGO_URI=mongodb://user:pass@host:27017 python scripts/init_db.py

Environment variables (or CLI flags) override defaults:
  MONGO_URI      — default: mongodb://localhost:27017
  MONGO_DB_NAME  — default: gridmind_ai
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Allow running from the project root without installing the package
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
except ImportError:
    print(
        "[ERROR] pymongo is not installed.  Run: pip install pymongo",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Collection → index specification map
# ---------------------------------------------------------------------------
# Each entry in the list is passed as keyword arguments to
#   collection.create_index(keys, **options)
# where *keys* is the first positional argument.
#
# MongoDB index docs:
#   https://www.mongodb.com/docs/manual/indexes/
# ---------------------------------------------------------------------------

COLLECTION_INDEXES: dict[str, list[dict[str, Any]]] = {
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    "users": [
        {
            "keys": [("username", ASCENDING)],
            "unique": True,
            "name": "uq_users_username",
        },
        {
            "keys": [("email", ASCENDING)],
            "unique": True,
            "name": "uq_users_email",
        },
        {
            "keys": [("role", ASCENDING)],
            "name": "idx_users_role",
        },
        {
            "keys": [("division_id", ASCENDING)],
            "name": "idx_users_division_id",
        },
        {
            "keys": [("is_active", ASCENDING)],
            "name": "idx_users_is_active",
        },
    ],
    # ------------------------------------------------------------------
    # divisions
    # ------------------------------------------------------------------
    "divisions": [
        {
            "keys": [("division_id", ASCENDING)],
            "unique": True,
            "name": "uq_divisions_division_id",
        },
        {
            "keys": [("name", ASCENDING)],
            "unique": True,
            "name": "uq_divisions_name",
        },
        {
            "keys": [("is_active", ASCENDING)],
            "name": "idx_divisions_is_active",
        },
    ],
    # ------------------------------------------------------------------
    # meters
    # ------------------------------------------------------------------
    "meters": [
        {
            "keys": [("meter_id", ASCENDING)],
            "unique": True,
            "name": "uq_meters_meter_id",
        },
        {
            "keys": [("division_id", ASCENDING)],
            "name": "idx_meters_division_id",
        },
        {
            "keys": [("is_active", ASCENDING)],
            "name": "idx_meters_is_active",
        },
    ],
    # ------------------------------------------------------------------
    # energy_data
    # ------------------------------------------------------------------
    "energy_data": [
        {
            "keys": [("meter_id", ASCENDING), ("timestamp", DESCENDING)],
            "name": "idx_energy_meter_ts",
        },
        {
            "keys": [("division_id", ASCENDING), ("timestamp", DESCENDING)],
            "name": "idx_energy_division_ts",
        },
        {
            "keys": [("timestamp", DESCENDING)],
            "name": "idx_energy_timestamp",
        },
        # Compound uniqueness: one reading per meter per timestamp
        {
            "keys": [("meter_id", ASCENDING), ("timestamp", ASCENDING)],
            "unique": True,
            "name": "uq_energy_meter_timestamp",
        },
    ],
    # ------------------------------------------------------------------
    # predictions
    # ------------------------------------------------------------------
    "predictions": [
        {
            "keys": [("division_id", ASCENDING), ("forecast_for", DESCENDING)],
            "name": "idx_predictions_division_forecast",
        },
        {
            "keys": [("generated_at", DESCENDING)],
            "name": "idx_predictions_generated_at",
        },
        {
            "keys": [("model_type", ASCENDING)],
            "name": "idx_predictions_model_type",
        },
    ],
    # ------------------------------------------------------------------
    # anomalies
    # ------------------------------------------------------------------
    "anomalies": [
        {
            "keys": [("meter_id", ASCENDING), ("detected_at", DESCENDING)],
            "name": "idx_anomalies_meter_detected",
        },
        {
            "keys": [("division_id", ASCENDING), ("detected_at", DESCENDING)],
            "name": "idx_anomalies_division_detected",
        },
        {
            "keys": [("is_resolved", ASCENDING)],
            "name": "idx_anomalies_is_resolved",
        },
        {
            "keys": [("anomaly_score", ASCENDING)],
            "name": "idx_anomalies_score",
        },
    ],
    # ------------------------------------------------------------------
    # alerts
    # ------------------------------------------------------------------
    "alerts": [
        {
            "keys": [("division_id", ASCENDING), ("created_at", DESCENDING)],
            "name": "idx_alerts_division_created",
        },
        {
            "keys": [("severity", ASCENDING)],
            "name": "idx_alerts_severity",
        },
        {
            "keys": [("is_acknowledged", ASCENDING)],
            "name": "idx_alerts_is_acknowledged",
        },
        {
            "keys": [("alert_type", ASCENDING)],
            "name": "idx_alerts_type",
        },
        {
            "keys": [("created_at", DESCENDING)],
            "name": "idx_alerts_created_at",
        },
    ],
    # ------------------------------------------------------------------
    # refresh_tokens
    # ------------------------------------------------------------------
    "refresh_tokens": [
        {
            "keys": [("token_hash", ASCENDING)],
            "unique": True,
            "name": "uq_refresh_tokens_token_hash",
        },
        {
            "keys": [("user_id", ASCENDING)],
            "name": "idx_refresh_tokens_user_id",
        },
        # TTL index — MongoDB auto-deletes expired tokens
        {
            "keys": [("expires_at", ASCENDING)],
            "expireAfterSeconds": 0,
            "name": "ttl_refresh_tokens_expires_at",
        },
        {
            "keys": [("is_revoked", ASCENDING)],
            "name": "idx_refresh_tokens_is_revoked",
        },
    ],
    # ------------------------------------------------------------------
    # audit_logs
    # ------------------------------------------------------------------
    "audit_logs": [
        {
            "keys": [("user_id", ASCENDING), ("timestamp", DESCENDING)],
            "name": "idx_audit_user_ts",
        },
        {
            "keys": [("action", ASCENDING)],
            "name": "idx_audit_action",
        },
        {
            "keys": [("timestamp", DESCENDING)],
            "name": "idx_audit_timestamp",
        },
        {
            "keys": [("resource_type", ASCENDING)],
            "name": "idx_audit_resource_type",
        },
        # TTL — keep audit logs for 1 year (365 days)
        {
            "keys": [("timestamp", ASCENDING)],
            "expireAfterSeconds": 365 * 24 * 3600,
            "name": "ttl_audit_logs_1yr",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_banner(title: str) -> None:
    border = "=" * 60
    print(f"\n{border}")
    print(f"  {title}")
    print(f"{border}")


def _ensure_collection(db: Any, name: str) -> Any:
    """
    Create *name* if it does not exist; return the Collection object.

    MongoDB creates collections implicitly on first write, but using
    ``create_collection`` lets us detect whether it was already there.
    """
    existing = db.list_collection_names()
    if name in existing:
        print(f"  [EXISTS]  collection '{name}'")
    else:
        db.create_collection(name)
        print(f"  [CREATED] collection '{name}'")
    return db[name]


def _create_indexes(collection: Any, index_specs: list[dict]) -> None:
    """Build all indexes defined for *collection*."""
    for spec in index_specs:
        spec = dict(spec)          # shallow copy so we don't mutate the constant
        keys = spec.pop("keys")
        name = spec.get("name", "?")
        try:
            result = collection.create_index(keys, **spec)
            print(f"      [INDEX]   {name!r:45s}  → {result}")
        except OperationFailure as exc:
            # A mismatch between existing index options is an error worth surfacing
            print(f"      [WARN]    {name!r}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main initialization routine
# ---------------------------------------------------------------------------

def init_db(mongo_uri: str, db_name: str) -> None:
    """Connect to MongoDB and initialize all collections and indexes."""
    print(f"\n[init_db] Connecting to MongoDB …  ({mongo_uri})")
    try:
        client: MongoClient = MongoClient(mongo_uri, serverSelectionTimeoutMS=5_000)
        client.admin.command("ping")
    except ConnectionFailure as exc:
        print(f"[ERROR] Cannot reach MongoDB at {mongo_uri!r}: {exc}", file=sys.stderr)
        sys.exit(1)

    db = client[db_name]
    print(f"[init_db] Connected.  Database: '{db_name}'")

    _print_banner("Step 1 — Ensuring collections exist")
    for col_name in COLLECTION_INDEXES:
        _ensure_collection(db, col_name)

    _print_banner("Step 2 — Creating indexes")
    total_indexes = 0
    for col_name, specs in COLLECTION_INDEXES.items():
        print(f"\n  Collection: {col_name}")
        _create_indexes(db[col_name], specs)
        total_indexes += len(specs)

    _print_banner("Summary")
    print(f"  Collections : {len(COLLECTION_INDEXES)}")
    print(f"  Index specs : {total_indexes}")
    print(f"  Database    : {db_name}")
    print(f"  URI         : {mongo_uri}")
    print(f"\n  ✓  Database initialization complete.\n")

    client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize GridMind AI MongoDB collections and indexes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mongo-uri",
        metavar="URI",
        default=None,
        help="MongoDB connection URI (overrides MONGO_URI env var). "
             "Default: mongodb://localhost:27017",
    )
    parser.add_argument(
        "--db-name",
        metavar="NAME",
        default=None,
        help="MongoDB database name (overrides MONGO_DB_NAME env var). "
             "Default: gridmind_ai",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    mongo_uri = args.mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = args.db_name or os.getenv("MONGO_DB_NAME", "gridmind_ai")

    print("\n=== GridMind AI — Database Initializer ===")
    init_db(mongo_uri=mongo_uri, db_name=db_name)


if __name__ == "__main__":
    main()
