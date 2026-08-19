"""Tests for the health probes and the tool call ingress endpoint."""

from fastapi.testclient import TestClient


def test_health(client: TestClient, api_prefix: str) -> None:
    response = client.get(f"{api_prefix}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready(client: TestClient, api_prefix: str) -> None:
    response = client.get(f"{api_prefix}/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_tool_call_valid(client: TestClient, api_prefix: str) -> None:
    response = client.post(
        f"{api_prefix}/tool-calls",
        json={
            "agent_id": "test-agent",
            "session_id": "test-session",
            "tool": "search_products",
            "parameters": {"query": "laptop"},
        },
    )

    assert response.status_code == 200


def test_tool_call_invalid(client: TestClient, api_prefix: str) -> None:
    response = client.post(f"{api_prefix}/tool-calls", json={"agent_id": "test-agent"})

    assert response.status_code == 422


def test_unknown_route_returns_error_envelope(
    client: TestClient, api_prefix: str
) -> None:
    response = client.get(f"{api_prefix}/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == "http_error"
