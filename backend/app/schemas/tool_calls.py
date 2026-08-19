"""Schemas for the tool call ingress endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import StrictModel

IDENTIFIER_MAX_LENGTH = 128


class ToolCallRequest(StrictModel):
    """A tool invocation submitted by an AI agent for inspection."""

    agent_id: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    session_id: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    tool: str = Field(min_length=1, max_length=IDENTIFIER_MAX_LENGTH)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    """Result of a tool executed through the gateway."""

    status: str = Field(default="success", examples=["success"])
    tool: str = Field(description="Name of the tool that produced the result.")
    result: dict[str, Any] = Field(description="Tool-specific output payload.")
