"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings, get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.rules.engine import get_waf_engine  # noqa: E402
from app.services.audit import get_audit_repository  # noqa: E402


@pytest.fixture(autouse=True)
def disable_api_auth_for_tests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep local .env API_AUTH_KEY from breaking the default test client."""
    base = get_settings()
    test_settings = base.model_copy(update={"api_auth_key": None})
    app.state.settings = test_settings
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def api_prefix() -> str:
    return get_settings().api_prefix


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_waf_state() -> Iterator[None]:
    """Give every test fresh in-memory WAF stores."""
    get_waf_engine.cache_clear()
    get_audit_repository.cache_clear()
    yield
    get_waf_engine.cache_clear()
    get_audit_repository.cache_clear()
