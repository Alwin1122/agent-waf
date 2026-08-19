"""Application services.

Hosts the tool gateway. WAF orchestration (tool call inspection, decision
recording) is introduced in later phases.
"""

from app.services.tool_gateway import ToolGateway, get_tool_gateway

__all__ = ["ToolGateway", "get_tool_gateway"]
