"""Controlled errors for idempotent protected-tool execution."""

from __future__ import annotations


class IdempotencyError(Exception):
    """Base error rendered by the API without exposing Redis details."""

    code = "idempotency_error"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IdempotencyConflictError(IdempotencyError):
    """The same client key was reused for a different request payload."""

    code = "idempotency_conflict"
    status_code = 409


class IdempotencyInProgressError(IdempotencyError):
    """A matching request did not complete within the bounded wait."""

    code = "idempotency_in_progress"
    status_code = 409


class IdempotencyUnavailableError(IdempotencyError):
    """Idempotency was requested without a persistent Redis store."""

    code = "idempotency_unavailable"
    status_code = 503
