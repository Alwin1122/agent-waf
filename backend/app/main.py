"""Application entrypoint for the Agent WAF gateway."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.lifecycle import lifespan
from app.logging_config import configure_logging, get_logger

DESCRIPTION = (
    "Security gateway that sits between an AI agent and its tools. Every tool "
    "invocation passes through this service for policy evaluation before "
    "the tool gateway executes it."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    if settings.allowed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_cors_origins),
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
            ],
        )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    get_logger(__name__).info(
        "%s v%s initialised "
        "(env=%s, api_prefix=%s, listen=%s:%d, cors_origins=%d)",
        settings.app_name,
        __version__,
        settings.app_env,
        settings.api_prefix,
        settings.host,
        settings.port,
        len(settings.allowed_cors_origins),
    )
    return app


app = create_app()
