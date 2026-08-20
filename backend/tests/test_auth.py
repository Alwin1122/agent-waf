"""Tests for optional API-key authentication on mutating endpoints."""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings, get_settings
from app.main import app

VALID_PAYLOAD = {
    "user_id": "user-1",
    "agent_id": "agent-1",
    "session_id": "session-1",
    "tool": "search_products",
    "parameters": {"query": "laptop"},
}


@pytest.fixture
def auth_client(disable_api_auth_for_tests: None) -> Iterator[TestClient]:
    configured = Settings(api_auth_key=SecretStr("test-secret-key"))
    app.state.settings = configured
    with TestClient(app) as client:
        yield client


def test_tool_call_rejects_missing_api_key_when_configured(
    auth_client: TestClient,
) -> None:
    api_prefix = auth_client.app.state.settings.api_prefix
    response = auth_client.post(f"{api_prefix}/tool-calls", json=VALID_PAYLOAD)

    assert response.status_code == 401


def test_tool_call_accepts_valid_api_key_when_configured(
    auth_client: TestClient,
) -> None:
    api_prefix = auth_client.app.state.settings.api_prefix
    response = auth_client.post(
        f"{api_prefix}/tool-calls",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "test-secret-key"},
    )

    assert response.status_code == 200


def test_agent_chat_rejects_invalid_api_key_when_configured(
    auth_client: TestClient,
) -> None:
    api_prefix = auth_client.app.state.settings.api_prefix
    response = auth_client.post(
        f"{api_prefix}/agent/chat",
        json={
            "user_id": "user-1",
            "agent_id": "shopping-agent",
            "session_id": "session-001",
            "message": "Hello",
        },
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 401
