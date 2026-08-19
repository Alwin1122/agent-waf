"""Application startup and shutdown for persistence dependencies."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.config import get_settings
from app.db.database import get_database
from app.db.migrations import migrate_audit_log_schema
from app.db.repositories import seed_core_records
from app.logging_config import get_logger
from app.redis_client import get_redis_client
from app.services.tool_gateway import get_tool_gateway

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize, verify and eventually close PostgreSQL and Redis."""
    settings = getattr(app.state, "settings", None) or get_settings()
    app.state.persistence_ready = not settings.persistence_enabled
    app.state.persistence_error = None
    logger.info(
        "Application startup: persistence_enabled=%s",
        settings.persistence_enabled,
    )

    database = None
    redis_client = None
    if settings.persistence_enabled:
        try:
            database = get_database()
            if settings.database_create_tables:
                database.create_schema()
            migrate_audit_log_schema(database.engine)
            database.check_connection()

            redis_client = get_redis_client()
            redis_client.check_connection()

            seed_core_records(
                database.session_factory,
                get_tool_gateway().list_tools(),
            )
            app.state.persistence_ready = True
            logger.info("PostgreSQL and Redis readiness checks passed")
        except Exception:
            app.state.persistence_error = "Persistence dependencies are unavailable"
            logger.exception("Persistence startup check failed")

    try:
        yield
    finally:
        logger.info("Application shutdown started")
        if redis_client is not None:
            redis_client.close()
        if database is not None:
            database.dispose()
        logger.info("Application shutdown complete")
