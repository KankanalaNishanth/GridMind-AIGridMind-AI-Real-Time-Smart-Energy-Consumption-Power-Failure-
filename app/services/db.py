"""
MongoDB connection management.

A single MongoClient is created at startup and reused for the life of
the process (PyMongo manages its own connection pool internally, so
there is no need to open/close a connection per-request).
"""
import logging
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def connect_to_mongo() -> None:
    """Open the MongoDB connection. Call once at app startup."""
    global _client, _db
    settings = get_settings()
    try:
        _client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client[settings.MONGO_DB_NAME]
        logger.info("Connected to MongoDB at %s (db=%s)", settings.MONGO_URI, settings.MONGO_DB_NAME)
    except ConnectionFailure as exc:
        logger.error("Could not connect to MongoDB at %s: %s", settings.MONGO_URI, exc)
        _client = None
        _db = None


def close_mongo_connection() -> None:
    """Close the MongoDB connection. Call once at app shutdown."""
    global _client
    if _client is not None:
        _client.close()
        logger.info("MongoDB connection closed")


def get_db() -> Optional[Database]:
    """Return the active database handle, or None if MongoDB isn't connected."""
    return _db
