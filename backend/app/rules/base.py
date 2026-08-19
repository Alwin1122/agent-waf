"""Base interface for independently configurable WAF rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from app.rules.models import RuleDecision, RuleResult, WAFRequest


class WAFRule(ABC):
    """A policy check run by the WAF engine before a tool executes."""

    name: ClassVar[str]

    @abstractmethod
    def evaluate(self, request: WAFRequest) -> RuleResult:
        """Inspect a tool call without executing it."""

    def record_success(self, request: WAFRequest) -> None:
        """Update state after the gateway successfully executes the call."""

    def record_failure(self, request: WAFRequest) -> None:
        """Release state reserved while evaluating a call that did not succeed."""

    def allow(self, reason: str) -> RuleResult:
        return RuleResult(
            rule=self.name,
            decision=RuleDecision.ALLOW,
            reason=reason,
        )

    def block(self, reason: str) -> RuleResult:
        return RuleResult(
            rule=self.name,
            decision=RuleDecision.BLOCK,
            reason=reason,
        )
