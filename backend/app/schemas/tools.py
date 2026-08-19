"""Schemas for the tool discovery endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDescriptor(BaseModel):
    """Public metadata describing one registered tool."""

    name: str = Field(examples=["search_products"])
    description: str
    parameters: dict[str, Any] = Field(
        description="JSON Schema for the tool's accepted parameters."
    )


class ToolListResponse(BaseModel):
    """Every tool the gateway is willing to invoke."""

    count: int
    tools: list[ToolDescriptor]
