"""Responses for audit history and aggregate WAF metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    timestamp: datetime
    request_id: str | None
    user_id: str | None = None
    agent_id: str
    session_id: str
    tool: str
    sanitized_parameters: dict[str, Any]
    rules_evaluated: list[dict[str, Any]]
    decision: Literal["ALLOW", "BLOCK", "WOULD_BLOCK"]
    reason: str
    enforcement_mode: Literal["ENFORCE", "SHADOW"]
    latency_ms: float


class AuditPageResponse(BaseModel):
    items: list[AuditEventResponse]
    page: int
    page_size: int
    total: int


class MetricsResponse(BaseModel):
    total_requests: int
    allowed: int
    blocked: int
    would_block: int
