from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.core.config import get_settings
from backend.app.db.mongo import lifespan_store
from backend.app.services.ml_service import GridMindModelService
from backend.app.services.telemetry_service import TelemetryService
from backend.app.services.websocket_manager import WebSocketManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_store() as store:
        model_service = GridMindModelService()
        app.state.store = store
        app.state.model_service = model_service
        app.state.telemetry_service = TelemetryService(store, model_service)
        app.state.websocket_manager = WebSocketManager()
        yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

