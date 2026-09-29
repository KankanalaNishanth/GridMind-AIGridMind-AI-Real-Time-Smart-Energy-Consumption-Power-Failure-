"""Health & readiness endpoints — used by load balancers, uptime checks, and you."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas import HealthResponse
from app.services.db import get_db
from app.services.model_registry import get_registry

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    registry = get_registry()
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        models_loaded=registry.is_ready(),
        database_connected=get_db() is not None,
    )
