"""API models for the sample OpenAI shopping agent."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.rules.models import RuleDecision
from app.schemas.common import StrictModel
from app.schemas.tool_calls import IDENTIFIER_MAX_LENGTH


class AgentChatRequest(StrictModel):
    agent_id: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    session_id: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    message: str = Field(min_length=1, max_length=8_000)


class AgentChatResponse(BaseModel):
    status: str = "success"
    response: str
    tool: str | None = None
    tool_result: dict[str, Any] | None = None


class AgentErrorResponse(BaseModel):
    status: str = "error"
    code: str
    message: str


class AgentWAFBlockResponse(BaseModel):
    status: str = "blocked"
    code: str = "waf_blocked"
    message: str = "Tool call blocked by Agent WAF."
    decision: RuleDecision = RuleDecision.BLOCK
    rule: str
    reason: str
