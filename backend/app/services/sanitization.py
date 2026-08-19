"""Sanitize tool parameters before persistence or API exposure."""

from __future__ import annotations

from typing import Any

MASK = "***MASKED***"
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "credential",
    "private_key",
)


def sanitize_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    """Return a detached structure with sensitive values masked recursively."""
    return {
        key: MASK if _is_sensitive_key(key) else _sanitize_value(value)
        for key, value in parameters.items()
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_parameters(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str) and _looks_like_credential(value):
        return MASK
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _looks_like_credential(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized.startswith(("bearer ", "sk-"))
