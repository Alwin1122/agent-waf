"""Controlled failures raised by the sample OpenAI agent."""

from __future__ import annotations

from app.rules.models import WAFDecision


class AgentError(Exception):
    """Base error rendered safely by the API exception handler."""

    code = "agent_error"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AgentConfigurationError(AgentError):
    code = "agent_not_configured"
    status_code = 503


class OpenAIProviderError(AgentError):
    code = "openai_error"
    status_code = 502


class InvalidModelToolCallError(AgentError):
    code = "invalid_model_tool_call"
    status_code = 502


class AgentToolExecutionError(AgentError):
    code = "agent_tool_execution_error"
    status_code = 502


class AgentWAFBlockedError(AgentError):
    code = "waf_blocked"
    status_code = 403

    def __init__(self, decision: WAFDecision) -> None:
        blocked = decision.blocked_by
        assert blocked is not None
        super().__init__(blocked.reason)
        self.decision = decision
        self.rule = blocked.rule
        self.reason = blocked.reason
