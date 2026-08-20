"""Optional API-key authentication for mutating ingress endpoints."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import Settings, get_settings


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Reject requests when ``API_AUTH_KEY`` is configured and the header is wrong."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    if settings.api_auth_key is None:
        return
    if x_api_key != settings.api_auth_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
