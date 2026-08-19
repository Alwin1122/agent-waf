"""Concurrent idempotency behavior on the protected execution path."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from time import sleep
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.redis_client import IdempotencyRecord, IdempotencyState
from app.rules import ParameterValidationRule, WAFRuleEngine
from app.schemas.tool_calls import ToolCallRequest
from app.services.audit import InMemoryAuditRepository
from app.services.idempotency import IdempotencyConflictError
from app.services.protected_tools import (
    ProtectedToolService,
    get_protected_tool_service,
)


class InMemoryIdempotencyState:
    """Thread-safe test double matching the Redis idempotency state machine."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, IdempotencyState, str | None]] = {}
        self._lock = Lock()

    def begin_request(
        self, idempotency_key: str, fingerprint: str
    ) -> IdempotencyRecord:
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is None:
                self._records[idempotency_key] = (
                    fingerprint,
                    IdempotencyState.RUNNING,
                    None,
                )
                return IdempotencyRecord(IdempotencyState.CLAIMED)
            existing_fingerprint, state, result = existing
            if existing_fingerprint != fingerprint:
                return IdempotencyRecord(IdempotencyState.CONFLICT)
            return IdempotencyRecord(state, result)

    def get_request(
        self, idempotency_key: str, fingerprint: str
    ) -> IdempotencyRecord | None:
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is None:
                return None
            existing_fingerprint, state, result = existing
            if existing_fingerprint != fingerprint:
                return IdempotencyRecord(IdempotencyState.CONFLICT)
            return IdempotencyRecord(state, result)

    def complete_request(
        self, idempotency_key: str, fingerprint: str, result: str
    ) -> None:
        with self._lock:
            self._records[idempotency_key] = (
                fingerprint,
                IdempotencyState.COMPLETED,
                result,
            )

    def release_request(self, idempotency_key: str, fingerprint: str) -> None:
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is not None and existing[0] == fingerprint:
                del self._records[idempotency_key]


def request(query: str = "laptop") -> ToolCallRequest:
    return ToolCallRequest(
        agent_id="agent-1",
        session_id="session-1",
        tool="search_products",
        parameters={"query": query},
    )


def test_concurrent_duplicate_requests_execute_tool_once() -> None:
    gateway = Mock()

    def execute(*args: object) -> dict:
        sleep(0.05)
        return {"execution": 1}

    gateway.execute.side_effect = execute
    service = ProtectedToolService(
        WAFRuleEngine([ParameterValidationRule()]),
        gateway,
        InMemoryAuditRepository(),
        idempotency_store=InMemoryIdempotencyState(),  # type: ignore[arg-type]
        idempotency_wait_timeout_seconds=5,
    )
    start = Barrier(10)

    def submit(_: int) -> dict | None:
        start.wait(timeout=5)
        return service.execute(
            request(),
            idempotency_key="same-key",
        ).result

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(submit, range(10)))

    assert gateway.execute.call_count == 1
    assert results == [{"execution": 1}] * 10


def test_same_key_with_different_payload_returns_conflict() -> None:
    gateway = Mock()
    gateway.execute.return_value = {"execution": 1}
    service = ProtectedToolService(
        WAFRuleEngine([ParameterValidationRule()]),
        gateway,
        InMemoryAuditRepository(),
        idempotency_store=InMemoryIdempotencyState(),  # type: ignore[arg-type]
    )
    service.execute(request(), idempotency_key="same-key")

    with pytest.raises(IdempotencyConflictError):
        service.execute(request("phone"), idempotency_key="same-key")

    gateway.execute.assert_called_once()


def test_tool_call_route_passes_idempotency_header(
    client: TestClient,
) -> None:
    service = Mock()
    service.execute.side_effect = IdempotencyConflictError(
        "Idempotency key was already used for a different request."
    )
    app.dependency_overrides[get_protected_tool_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/tool-calls",
            headers={"Idempotency-Key": "same-key"},
            json=request().model_dump(mode="json"),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"
    service.execute.assert_called_once()
    assert service.execute.call_args.kwargs["idempotency_key"] == "same-key"
