from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from backend.app.core.config import get_settings


class MongoStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=1500)
        self.db: Database = self.client[settings.mongo_db]

    @property
    def telemetry(self) -> Collection:
        return self.db["telemetry"]

    @property
    def predictions(self) -> Collection:
        return self.db["predictions"]

    @property
    def alerts(self) -> Collection:
        return self.db["alerts"]

    def ensure_indexes(self) -> None:
        self.telemetry.create_index("timestamp")
        self.telemetry.create_index([("circle", 1), ("division", 1)])
        self.predictions.create_index("timestamp")
        self.alerts.create_index("timestamp")

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def close(self) -> None:
        self.client.close()


@asynccontextmanager
async def lifespan_store() -> AsyncIterator[MongoStore]:
    store = MongoStore()
    if store.ping():
        store.ensure_indexes()
    try:
        yield store
    finally:
        store.close()

