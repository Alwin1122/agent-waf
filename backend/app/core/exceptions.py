"""Global exception handlers producing a consistent JSON error envelope."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger
from app.schemas.common import ErrorDetail, ErrorResponse
from app.services.agent_errors import AgentError, AgentWAFBlockedError
from app.tools.errors import ToolError

logger = get_logger(__name__)

INTERNAL_ERROR_MESSAGE = "An internal error occurred while processing the request."


def _json_error(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(code=code, message=message, details=details or [])
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _to_error_details(errors: list[dict]) -> list[ErrorDetail]:
    return [
        ErrorDetail(
            location=".".join(str(part) for part in error.get("loc", ())),
            message=str(error.get("msg", "Invalid value.")),
            type=str(error.get("type", "validation_error")),
        )
        for error in errors
    ]


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return HTTP 422 with per-field validation details."""
    logger.info(
        "Request validation failed: %s %s (%d issues)",
        request.method,
        request.url.path,
        len(exc.errors()),
    )
    return _json_error(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed.",
        _to_error_details(exc.errors()),
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Convert framework HTTP errors into the shared error envelope."""
    return _json_error(
        exc.status_code,
        "http_error",
        str(exc.detail),
    )


async def handle_tool_error(request: Request, exc: ToolError) -> JSONResponse:
    """Surface a controlled tool-layer failure using its own code and status."""
    logger.info(
        "Tool error during %s %s: %s (%s)",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
    )
    return _json_error(
        exc.status_code,
        exc.code,
        exc.message,
        [ErrorDetail(**detail) for detail in exc.details],
    )


async def handle_agent_error(request: Request, exc: AgentError) -> JSONResponse:
    """Return provider and orchestration failures without leaking internals."""
    logger.info(
        "Agent request failed: %s %s code=%s",
        request.method,
        request.url.path,
        exc.code,
    )
    if isinstance(exc, AgentWAFBlockedError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "blocked",
                "code": exc.code,
                "message": "Tool call blocked by Agent WAF.",
                "decision": "BLOCK",
                "rule": exc.rule,
                "reason": exc.reason,
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.code,
            "message": exc.message,
        },
    )


async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """Log the real failure and return an opaque HTTP 500 to the caller."""
    logger.exception(
        "Unhandled exception during %s %s", request.method, request.url.path
    )
    return _json_error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_server_error",
        INTERNAL_ERROR_MESSAGE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all error handlers to the application."""
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ToolError, handle_tool_error)
    app.add_exception_handler(AgentError, handle_agent_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_exception)
