"""Liveness and readiness endpoints."""

from fastapi import APIRouter, HTTPException, Request, status

from app.config import Settings, get_settings
from app.db.database import get_database
from app.logging_config import get_logger
from app.redis_client import get_redis_client
from app.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def get_health() -> HealthResponse:
    """Report that the process is running and able to serve requests."""
    return HealthResponse(status="healthy")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
def get_readiness(request: Request) -> ReadinessResponse:
    """Run live PostgreSQL and Redis checks when persistence is enabled."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    if settings.persistence_enabled:
        try:
            _check_persistence_dependencies()
            request.app.state.persistence_ready = True
            request.app.state.persistence_error = None
        except Exception as exc:
            request.app.state.persistence_ready = False
            request.app.state.persistence_error = (
                "Persistence dependencies are unavailable"
            )
            logger.warning(
                "Readiness dependency check failed: %s",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Persistence dependencies are unavailable.",
            ) from exc
    elif not getattr(request.app.state, "persistence_ready", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistence dependencies are unavailable.",
        )
    return ReadinessResponse(status="ready")


def _check_persistence_dependencies() -> None:
    get_database().check_connection()
    get_redis_client().check_connection()
