"""Structured inputs and decisions shared by all WAF rules."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleDecision(str, Enum):
    """The only outcomes a WAF rule may return."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class WAFRequest(BaseModel):
    """Tool call context inspected by the WAF."""

    model_config = ConfigDict(frozen=True)

    agent_id: str
    session_id: str
    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class RuleResult(BaseModel):
    """One rule's structured decision."""

    rule: str
    decision: RuleDecision
    reason: str


class WAFDecision(BaseModel):
    """Aggregate result produced by the rule engine."""

    decision: RuleDecision
    results: list[RuleResult]
    blocked_by: RuleResult | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is RuleDecision.ALLOW


class WAFBlockResponse(BaseModel):
    """Response returned when the WAF prevents tool execution."""

    status: str = "blocked"
    code: str = "waf_blocked"
    decision: RuleDecision = RuleDecision.BLOCK
    rule: str
    reason: str
