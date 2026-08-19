"""Per-agent, per-tool sliding-window rate limiting."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from app.rules.base import WAFRule
from app.rules.models import RuleResult, WAFRequest
from app.rules.stores import RateLimitStore


@dataclass(frozen=True)
class RateLimit:
    """Maximum successful calls permitted within a sliding window."""

    max_calls: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.max_calls < 1 or self.window_seconds < 1:
            raise ValueError("Rate-limit values must be positive.")


class RateLimitRule(WAFRule):
    """Limit completed calls independently for each agent/tool pair."""

    name = "rate_limit"

    def __init__(
        self,
        limits: Mapping[str, RateLimit],
        store: RateLimitStore,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = dict(limits)
        self._store = store
        self._clock = clock
        self._reservations: dict[int, tuple[str, str]] = {}
        self._reservations_lock = Lock()

    def evaluate(self, request: WAFRequest) -> RuleResult:
        limit = self._limits.get(request.tool)
        if limit is None:
            return self.allow("No rate limit configured for this tool")

        key = self._key(request)
        reservation_id = uuid4().hex
        reserved = self._store.reserve(
            key,
            reservation_id,
            self._clock(),
            max_calls=limit.max_calls,
            window_seconds=limit.window_seconds,
        )
        if not reserved:
            return self.block(
                f"Rate limit exceeded: maximum {limit.max_calls} calls "
                f"per {limit.window_seconds} seconds"
            )
        with self._reservations_lock:
            self._reservations[id(request)] = (key, reservation_id)
        return self.allow("Within allowed limit")

    def record_success(self, request: WAFRequest) -> None:
        if request.tool not in self._limits:
            return
        reservation = self._pop_reservation(request)
        key = self._key(request)
        reservation_id = reservation[1] if reservation is not None else uuid4().hex
        self._store.commit(key, reservation_id, self._clock())

    def record_failure(self, request: WAFRequest) -> None:
        reservation = self._pop_reservation(request)
        if reservation is not None:
            key, reservation_id = reservation
            self._store.release(key, reservation_id)

    def _pop_reservation(self, request: WAFRequest) -> tuple[str, str] | None:
        with self._reservations_lock:
            return self._reservations.pop(id(request), None)

    @staticmethod
    def _key(request: WAFRequest) -> str:
        return f"{request.agent_id}\x1f{request.tool}"
