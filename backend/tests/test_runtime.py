"""Production runtime, readiness, and CORS configuration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import health as health_routes
from app.config import Settings
from app.main import create_app


def persistent_settings() -> Settings:
    return Settings(
        persistence_enabled=True,
        database_url="postgresql+psycopg://user:password@postgres/db",
        redis_url="redis://:password@redis:6379/0",
    )


def test_runtime_host_and_port_defaults() -> None:
    settings = Settings()

    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


def test_runtime_port_is_environment_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORT", "9000")

    assert Settings().port == 9000


def test_readiness_runs_live_dependency_checks(
    client: TestClient,
    api_prefix: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks = 0

    def successful_check() -> None:
        nonlocal checks
        checks += 1

    original_settings = client.app.state.settings
    original_ready = client.app.state.persistence_ready
    client.app.state.settings = persistent_settings()
    monkeypatch.setattr(
        health_routes,
        "_check_persistence_dependencies",
        successful_check,
    )
    try:
        response = client.get(f"{api_prefix}/ready")
    finally:
        client.app.state.settings = original_settings
        client.app.state.persistence_ready = original_ready

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert checks == 1


def test_readiness_returns_503_when_live_check_fails(
    client: TestClient,
    api_prefix: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_check() -> None:
        raise ConnectionError("dependency unavailable")

    original_settings = client.app.state.settings
    original_ready = client.app.state.persistence_ready
    client.app.state.settings = persistent_settings()
    monkeypatch.setattr(
        health_routes,
        "_check_persistence_dependencies",
        failed_check,
    )
    try:
        response = client.get(f"{api_prefix}/ready")
    finally:
        client.app.state.settings = original_settings
        client.app.state.persistence_ready = original_ready

    assert response.status_code == 503
    assert response.json()["message"] == "Persistence dependencies are unavailable."


def test_cors_allows_only_configured_frontend_origin() -> None:
    app = create_app(
        Settings(
            cors_allowed_origins=(
                "https://dashboard.example.com,https://admin.example.com"
            )
        )
    )

    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/metrics",
            headers={
                "Origin": "https://dashboard.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/api/v1/metrics",
            headers={
                "Origin": "https://untrusted.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert (
        allowed.headers["access-control-allow-origin"]
        == "https://dashboard.example.com"
    )
    assert "access-control-allow-origin" not in denied.headers


def test_cors_rejects_wildcard_with_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(
            cors_allowed_origins="*",
            cors_allow_credentials=True,
        )
