"""Replaceable storage contracts and in-memory Phase 3 adapters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from threading import Lock
from typing import Protocol
from uuid import uuid4


class RateLimitStore(Protocol):
    """Storage required by the rate-limit rule."""

    def reserve(
        self,
        key: str,
        reservation_id: str,
        timestamp: float,
        *,
        max_calls: int,
        window_seconds: int,
    ) -> bool:
        """Atomically reserve capacity when the sliding window is below its limit."""

    def commit(self, key: str, reservation_id: str, timestamp: float) -> None:
        """Persist a successful call, creating the reservation when needed."""

    def release(self, key: str, reservation_id: str) -> None:
        """Remove a reservation for a call that did not execute successfully."""

    def count_since(self, key: str, since: float) -> int:
        """Count recorded calls at or after ``since``."""

    def add(self, key: str, timestamp: float) -> None:
        """Record a completed call."""


class AgentScopeStore(Protocol):
    """Source of data scopes assigned to agents."""

    def get_customer_ids(self, agent_id: str) -> frozenset[str] | None:
        """Return allowed customer ids, or ``None`` when no scope is declared."""


class SequenceStateStore(Protocol):
    """Session history required by sequence enforcement."""

    def get_completed_tools(self, agent_id: str, session_id: str) -> tuple[str, ...]:
        """Return successfully completed tools in execution order."""

    def record_completed_tool(
        self, agent_id: str, session_id: str, tool: str
    ) -> None:
        """Append one successfully completed tool."""


class InMemoryRateLimitStore:
    """Thread-safe sliding-window timestamps.

    A Redis adapter can implement ``RateLimitStore`` without changing the rule.
    """

    def __init__(self) -> None:
        self._calls: dict[str, dict[str, float]] = defaultdict(dict)
        self._lock = Lock()

    def reserve(
        self,
        key: str,
        reservation_id: str,
        timestamp: float,
        *,
        max_calls: int,
        window_seconds: int,
    ) -> bool:
        with self._lock:
            calls = self._calls[key]
            self._remove_expired(calls, timestamp - window_seconds)
            if len(calls) >= max_calls:
                return False
            calls[reservation_id] = timestamp
            return True

    def commit(self, key: str, reservation_id: str, timestamp: float) -> None:
        with self._lock:
            self._calls[key][reservation_id] = timestamp

    def release(self, key: str, reservation_id: str) -> None:
        with self._lock:
            self._calls[key].pop(reservation_id, None)

    def count_since(self, key: str, since: float) -> int:
        with self._lock:
            calls = self._calls[key]
            self._remove_expired(calls, since)
            return len(calls)

    def add(self, key: str, timestamp: float) -> None:
        self.commit(key, uuid4().hex, timestamp)

    def clear(self) -> None:
        with self._lock:
            self._calls.clear()

    @staticmethod
    def _remove_expired(calls: dict[str, float], since: float) -> None:
        for reservation_id in [
            reservation_id
            for reservation_id, timestamp in calls.items()
            if timestamp < since
        ]:
            del calls[reservation_id]


class InMemoryAgentScopeStore:
    """In-memory agent scopes, replaceable by PostgreSQL in Phase 4."""

    def __init__(
        self, scopes: dict[str, Iterable[str]] | None = None
    ) -> None:
        self._scopes = {
            agent_id: frozenset(customer_ids)
            for agent_id, customer_ids in (scopes or {}).items()
        }

    def get_customer_ids(self, agent_id: str) -> frozenset[str] | None:
        return self._scopes.get(agent_id)

    def set_customer_ids(
        self, agent_id: str, customer_ids: Iterable[str]
    ) -> None:
        self._scopes[agent_id] = frozenset(customer_ids)


class InMemorySequenceStateStore:
    """Thread-safe successful-call history for each agent session."""

    def __init__(self) -> None:
        self._history: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._lock = Lock()

    def get_completed_tools(self, agent_id: str, session_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._history[(agent_id, session_id)])

    def record_completed_tool(
        self, agent_id: str, session_id: str, tool: str
    ) -> None:
        with self._lock:
            self._history[(agent_id, session_id)].append(tool)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
