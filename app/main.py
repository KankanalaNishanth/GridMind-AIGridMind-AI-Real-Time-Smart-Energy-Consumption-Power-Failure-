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
from fastapi.openapi.utils import get_openapi

from app.core.config import BASE_DIR, get_settings
from app.core.logging_config import configure_logging
# Existing routers (preserved)
from app.routers import auth, dashboard, data, evaluate, health, predict, stream
# New RBAC routers
from app.routers import auth_rbac, public, ae, de, common
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

    # Create MongoDB indexes for RBAC collections
    from app.services.db import get_db
    db = get_db()
    if db is not None:
        try:
            from app.database.mongodb import setup_indexes
            setup_indexes(db)
            logger.info("MongoDB indexes initialized.")
        except Exception as exc:
            logger.warning("Index setup skipped: %s", exc)

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
        description=(
            "Real-Time Smart Energy Consumption & Power Failure Prediction System\n\n"
            "## API Sections\n"
            "| Prefix | Access | Description |\n"
            "|--------|--------|-------------|\n"
            "| `/api/v1/public/*` | PUBLIC (no auth) | Energy stats, trends, public alerts |\n"
            "| `/api/v1/auth/*` | PUBLIC | Login, logout, token refresh |\n"
            "| `/api/v1/ae/*` | AE + DE | Assistant Engineer operations |\n"
            "| `/api/v1/de/*` | DE only | Divisional Engineer operations |\n"
            "| `/api/v1/common/*` | AE + DE | Shared profile & password |\n"
        ),
        lifespan=lifespan,
        # Enable JWT Bearer in Swagger UI
        openapi_tags=[
            {"name": "Public", "description": "Unauthenticated public endpoints"},
            {"name": "Authentication", "description": "Login, logout, token management"},
            {"name": "AE — Assistant Engineer", "description": "Requires AE or DE role"},
            {"name": "DE — Divisional Engineer", "description": "Requires DE role"},
            {"name": "Common — Authenticated Users", "description": "Requires AE or DE role"},
            {"name": "Predictions", "description": "ML prediction endpoints (AE/DE)"},
            {"name": "Dashboard", "description": "Analytics dashboard (AE/DE)"},
            {"name": "Data", "description": "Energy & alert data (AE/DE)"},
            {"name": "Stream Simulation", "description": "Kafka stream simulation (DE)"},
            {"name": "Evaluate", "description": "ML model evaluation (DE)"},
            {"name": "Health", "description": "Service health check"},
        ],
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # ----------------------------------------------------------------
    # NEW RBAC routers (register BEFORE legacy routers so /auth/login
    # from auth_rbac.py takes precedence over the legacy /auth/login)
    # ----------------------------------------------------------------
    api_prefix = settings.API_PREFIX  # /api/v1

    app.include_router(public.router, prefix=api_prefix)
    app.include_router(auth_rbac.router, prefix=api_prefix)
    app.include_router(ae.router, prefix=api_prefix)
    app.include_router(de.router, prefix=api_prefix)
    app.include_router(common.router, prefix=api_prefix)

    # ----------------------------------------------------------------
    # Existing ML / pipeline routers (unchanged — RBAC added above)
    # ----------------------------------------------------------------
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(predict.router, prefix=api_prefix)
    app.include_router(data.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)
    app.include_router(stream.router, prefix=api_prefix)
    app.include_router(evaluate.router, prefix=api_prefix)

    # Legacy auth router (kept for backward compatibility)
    app.include_router(auth.router, prefix=api_prefix)

    # --- Static frontend files ---
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
            "message": "GridMind AI API is online.",
            "docs": "/docs",
            "public_api": f"{api_prefix}/public/energy-summary",
            "login": f"{api_prefix}/auth/login",
        }

    return app


app = create_app()
