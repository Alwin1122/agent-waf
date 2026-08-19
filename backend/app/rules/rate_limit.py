"""Per-agent, per-tool sliding-window rate limiting."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

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

    def evaluate(self, request: WAFRequest) -> RuleResult:
        limit = self._limits.get(request.tool)
        if limit is None:
            return self.allow("No rate limit configured for this tool")

        count = self._store.count_since(
            self._key(request), self._clock() - limit.window_seconds
        )
        if count >= limit.max_calls:
            return self.block(
                f"Rate limit exceeded: maximum {limit.max_calls} calls "
                f"per {limit.window_seconds} seconds"
            )
        return self.allow("Within allowed limit")

    def record_success(self, request: WAFRequest) -> None:
        if request.tool in self._limits:
            self._store.add(self._key(request), self._clock())

    @staticmethod
    def _key(request: WAFRequest) -> str:
        return f"{request.agent_id}\x1f{request.tool}"
