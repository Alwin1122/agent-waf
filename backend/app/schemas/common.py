"""Schemas shared across the API surface."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model for inbound payloads.

    Unknown fields are rejected so malformed agent traffic fails fast instead
    of being silently ignored by the gateway.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(default="healthy", examples=["healthy"])


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    status: str = Field(default="ready", examples=["ready"])


class ErrorDetail(BaseModel):
    """A single field-level validation problem."""

    location: str = Field(description="Dotted path to the offending field.")
    message: str = Field(description="Human readable explanation.")
    type: str = Field(description="Machine readable validation error type.")


class ErrorResponse(BaseModel):
    """Uniform error envelope returned by every failing request."""

    status: str = Field(default="error")
    code: str = Field(description="Stable, machine readable error code.")
    message: str = Field(description="Human readable error summary.")
    details: list[ErrorDetail] = Field(default_factory=list)
