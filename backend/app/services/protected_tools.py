"""Single protected execution path shared by APIs and AI agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Any, Callable, Protocol
from uuid import uuid4

from fastapi import Depends

from app.config import get_settings
from app.rules.engine import WAFRuleEngine, get_waf_engine
from app.rules.models import WAFDecision, WAFRequest
from app.schemas.tool_calls import ToolCallRequest
from app.services.audit import AuditRepository, get_audit_repository
from app.services.sanitization import sanitize_parameters
from app.services.tool_gateway import ToolGateway, get_tool_gateway


class EnforcementMode(str, Enum):
    ENFORCE = "ENFORCE"
    SHADOW = "SHADOW"


class AuditDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WOULD_BLOCK = "WOULD_BLOCK"


@dataclass(frozen=True)
class ProtectedToolOutcome:
    """Result of WAF inspection and optional gateway execution."""

    decision: WAFDecision
    tool: str
    result: dict[str, Any] | None = None
    effective_decision: AuditDecision | None = None
    enforcement_mode: EnforcementMode = EnforcementMode.ENFORCE
    request_id: str | None = None

    @property
    def allowed(self) -> bool:
        if self.effective_decision is None:
            return self.decision.allowed
        return self.effective_decision is not AuditDecision.BLOCK


class ProtectedToolCaller(Protocol):
    """Narrow interface available to the OpenAI agent."""

    def list_tools(self) -> list[dict[str, Any]]: ...

    def execute(self, request: ToolCallRequest) -> ProtectedToolOutcome: ...


class ProtectedToolService:
    """Always evaluate WAF rules before allowing ToolGateway execution."""

    def __init__(
        self,
        waf: WAFRuleEngine,
        gateway: ToolGateway,
        audit: AuditRepository,
        *,
        enforcement_mode: EnforcementMode = EnforcementMode.ENFORCE,
        clock: Callable[[], float] = monotonic,
        request_id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._waf = waf
        self._gateway = gateway
        self._audit = audit
        self._enforcement_mode = enforcement_mode
        self._clock = clock
        self._request_id_factory = request_id_factory

    def list_tools(self) -> list[dict[str, Any]]:
        return self._gateway.list_tools()

    def execute(self, request: ToolCallRequest) -> ProtectedToolOutcome:
        started_at = self._clock()
        request_id = self._request_id_factory()
        waf_request = WAFRequest(
            agent_id=request.agent_id,
            session_id=request.session_id,
            tool=request.tool,
            parameters=request.parameters,
        )
        decision = self._waf.evaluate(waf_request)
        blocked = decision.blocked_by
        if blocked is not None:
            effective_decision = (
                AuditDecision.BLOCK
                if self._enforcement_mode is EnforcementMode.ENFORCE
                else AuditDecision.WOULD_BLOCK
            )
            reason = blocked.reason
        else:
            effective_decision = AuditDecision.ALLOW
            reason = "All WAF rules allowed the request"

        if effective_decision is AuditDecision.BLOCK:
            self._record_audit(
                request=request,
                decision=decision,
                effective_decision=effective_decision,
                reason=reason,
                request_id=request_id,
                started_at=started_at,
            )
            return ProtectedToolOutcome(
                decision=decision,
                tool=request.tool,
                effective_decision=effective_decision,
                enforcement_mode=self._enforcement_mode,
                request_id=request_id,
            )

        try:
            result = self._gateway.execute(request.tool, request.parameters)
        except Exception:
            failure_reason = (
                reason
                if effective_decision is AuditDecision.WOULD_BLOCK
                else "WAF allowed the request, but tool execution failed"
            )
            self._record_audit(
                request=request,
                decision=decision,
                effective_decision=effective_decision,
                reason=failure_reason,
                request_id=request_id,
                started_at=started_at,
            )
            raise

        self._waf.record_success(waf_request)
        self._record_audit(
            request=request,
            decision=decision,
            effective_decision=effective_decision,
            reason=reason,
            request_id=request_id,
            started_at=started_at,
        )
        return ProtectedToolOutcome(
            decision=decision,
            tool=request.tool,
            result=result,
            effective_decision=effective_decision,
            enforcement_mode=self._enforcement_mode,
            request_id=request_id,
        )

    def _record_audit(
        self,
        *,
        request: ToolCallRequest,
        decision: WAFDecision,
        effective_decision: AuditDecision,
        reason: str,
        request_id: str,
        started_at: float,
    ) -> None:
        blocked = decision.blocked_by
        self._audit.record(
            request_id=request_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            tool_name=request.tool,
            sanitized_parameters=sanitize_parameters(request.parameters),
            rules_evaluated=[
                result.model_dump(mode="json") for result in decision.results
            ],
            decision=effective_decision.value,
            rule=blocked.rule if blocked is not None else None,
            reason=reason,
            enforcement_mode=self._enforcement_mode.value,
            latency_ms=round((self._clock() - started_at) * 1_000, 3),
        )


def get_protected_tool_service(
    waf: WAFRuleEngine = Depends(get_waf_engine),
    gateway: ToolGateway = Depends(get_tool_gateway),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ProtectedToolService:
    mode = EnforcementMode(get_settings().waf_enforcement_mode)
    return ProtectedToolService(
        waf,
        gateway,
        audit,
        enforcement_mode=mode,
    )
