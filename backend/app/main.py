"""
GridMind AI — FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000

Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
"""
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import BASE_DIR, get_settings
from app.core.logging_config import configure_logging
from app.routers import dashboard, data, evaluate, health, predict, stream
from app.services.db import close_mongo_connection, connect_to_mongo
from app.services.model_registry import load_all_models

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting GridMind AI backend...")
    load_all_models()
    connect_to_mongo()
    logger.info("Startup complete.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down GridMind AI backend...")
    close_mongo_connection()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Real-Time Smart Energy Consumption & Power Failure Prediction System",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(predict.router, prefix=settings.API_PREFIX)
    app.include_router(data.router, prefix=settings.API_PREFIX)
    app.include_router(dashboard.router, prefix=settings.API_PREFIX)
    app.include_router(stream.router, prefix=settings.API_PREFIX)
    app.include_router(evaluate.router, prefix=settings.API_PREFIX)

    frontend_dir = BASE_DIR / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
        css_dir = frontend_dir / "css"
        if css_dir.exists():
            app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")
        js_dir = frontend_dir / "js"
        if js_dir.exists():
            app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = BASE_DIR / "frontend" / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {
            "message": "GridMind AI API is online. Place index.html inside the frontend/ folder.",
            "docs": "/docs"
        }

    return app


app = create_app()
