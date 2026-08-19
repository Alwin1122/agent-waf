"""Persistence-independent audit recording service."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from app.config import get_settings
from app.db.database import get_database
from app.db.repositories import PostgresAuditRepository


class AuditRepository(Protocol):
    def record(
        self,
        *,
        agent_id: str,
        session_id: str,
        tool_name: str,
        decision: str,
        reason: str,
        rule: str | None = None,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
        sanitized_parameters: dict[str, Any] | None = None,
        rules_evaluated: list[dict[str, Any]] | None = None,
        enforcement_mode: str = "ENFORCE",
        latency_ms: float = 0.0,
    ) -> None: ...

    def list_events(
        self, *, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]: ...

    def metrics(self) -> dict[str, int]: ...


class InMemoryAuditRepository:
    """Thread-safe test/development adapter with production-equivalent queries."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._lock = Lock()

    def record(
        self,
        *,
        agent_id: str,
        session_id: str,
        tool_name: str,
        decision: str,
        reason: str,
        rule: str | None = None,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
        sanitized_parameters: dict[str, Any] | None = None,
        rules_evaluated: list[dict[str, Any]] | None = None,
        enforcement_mode: str = "ENFORCE",
        latency_ms: float = 0.0,
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc),
            "request_id": request_id or str(uuid4()),
            "agent_id": agent_id,
            "session_id": session_id,
            "tool": tool_name,
            "sanitized_parameters": sanitized_parameters or {},
            "rules_evaluated": rules_evaluated or [],
            "decision": decision,
            "reason": reason,
            "enforcement_mode": enforcement_mode,
            "latency_ms": latency_ms,
        }
        with self._lock:
            self._events.append(event)

    def list_events(
        self, *, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            newest_first = list(reversed(self._events))
            return newest_first[offset : offset + limit], len(self._events)

    def metrics(self) -> dict[str, int]:
        with self._lock:
            decisions = [event["decision"] for event in self._events]
        return {
            "total_requests": len(decisions),
            "allowed": decisions.count("ALLOW"),
            "blocked": decisions.count("BLOCK"),
            "would_block": decisions.count("WOULD_BLOCK"),
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


@lru_cache
def get_audit_repository() -> AuditRepository:
    """Return PostgreSQL auditing or an isolated in-memory adapter."""
    if not get_settings().persistence_enabled:
        return InMemoryAuditRepository()
    return PostgresAuditRepository(get_database().session_factory)
