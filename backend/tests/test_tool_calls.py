"""Tests for the tool call ingress and tool discovery endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

VALID_PAYLOAD: dict[str, Any] = {
    "agent_id": "agent-1",
    "session_id": "session-1",
    "tool": "search_products",
    "parameters": {"query": "laptop"},
}


def test_valid_tool_call_is_executed(client: TestClient, api_prefix: str) -> None:
    response = client.post(f"{api_prefix}/tool-calls", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["tool"] == "search_products"
    assert body["result"]["count"] == 2


def test_tool_call_reaches_each_registered_tool(
    client: TestClient, api_prefix: str
) -> None:
    payload = {
        **VALID_PAYLOAD,
        "tool": "get_customer",
        "parameters": {"customer_id": "c-001"},
    }

    response = client.post(f"{api_prefix}/tool-calls", json=payload)

    assert response.status_code == 200
    assert response.json()["result"]["customer"]["name"] == "Ada Lovelace"


def test_unknown_tool_is_rejected(client: TestClient, api_prefix: str) -> None:
    payload = {**VALID_PAYLOAD, "tool": "delete_everything"}

    response = client.post(f"{api_prefix}/tool-calls", json=payload)

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == "tool_not_found"
    assert "delete_everything" in body["message"]


def test_omitted_parameters_fail_the_tool_schema(
    client: TestClient, api_prefix: str
) -> None:
    payload = {key: value for key, value in VALID_PAYLOAD.items() if key != "parameters"}

    response = client.post(f"{api_prefix}/tool-calls", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "tool_input_error"
    assert any(detail["location"] == "parameters.query" for detail in body["details"])


def test_controlled_tool_failure_uses_the_error_envelope(
    client: TestClient, api_prefix: str
) -> None:
    payload = {
        **VALID_PAYLOAD,
        "tool": "get_customer",
        "parameters": {"customer_id": "c-999"},
    }

    response = client.post(f"{api_prefix}/tool-calls", json=payload)

    assert response.status_code == 404
    assert response.json()["code"] == "customer_not_found"


@pytest.mark.parametrize(
    ("payload", "invalid_field"),
    [
        ({**VALID_PAYLOAD, "tool": ""}, "tool"),
        ({key: v for key, v in VALID_PAYLOAD.items() if key != "agent_id"}, "agent_id"),
        ({**VALID_PAYLOAD, "parameters": "not-an-object"}, "parameters"),
        ({**VALID_PAYLOAD, "unexpected": "value"}, "unexpected"),
    ],
    ids=["empty-tool", "missing-agent-id", "wrong-parameters-type", "extra-field"],
)
def test_invalid_tool_call_is_rejected(
    client: TestClient, api_prefix: str, payload: dict[str, Any], invalid_field: str
) -> None:
    response = client.post(f"{api_prefix}/tool-calls", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert any(invalid_field in detail["location"] for detail in body["details"])


def test_list_tools_returns_every_registered_tool(
    client: TestClient, api_prefix: str
) -> None:
    response = client.get(f"{api_prefix}/tools")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert [tool["name"] for tool in body["tools"]] == [
        "create_order",
        "get_customer",
        "search_products",
    ]


def test_listed_tools_expose_a_parameter_schema(
    client: TestClient, api_prefix: str
) -> None:
    response = client.get(f"{api_prefix}/tools")

    tools = {tool["name"]: tool for tool in response.json()["tools"]}
    assert set(tools["create_order"]["parameters"]["required"]) == {
        "customer_id",
        "product_id",
        "quantity",
    }
    assert tools["search_products"]["description"]
