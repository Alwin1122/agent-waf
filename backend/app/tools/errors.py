"""Errors raised by the tool layer.

Each error carries the HTTP status and stable error code the API should
surface, so the tool layer never has to import FastAPI.
"""

from __future__ import annotations

from typing import Any


class ToolError(Exception):
    """Base class for every failure originating inside the tool layer."""

    code = "tool_error"
    status_code = 400

    def __init__(
        self, message: str, *, details: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class ToolNotFoundError(ToolError):
    """Raised when a caller asks the registry for an unregistered tool."""

    code = "tool_not_found"
    status_code = 404


class DuplicateToolError(ToolError):
    """Raised when two tools claim the same name.

    This is a wiring mistake rather than bad caller input, so it maps to a
    server-side failure.
    """

    code = "duplicate_tool"
    status_code = 500


class ToolInputError(ToolError):
    """Raised when parameters fail a tool's own schema validation."""

    code = "tool_input_error"
    status_code = 422


class ToolExecutionError(ToolError):
    """Raised for controlled, expected failures while a tool runs.

    Tools use this to report domain outcomes such as a missing customer,
    keeping them distinct from unexpected crashes.
    """

    code = "tool_execution_error"
    status_code = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
