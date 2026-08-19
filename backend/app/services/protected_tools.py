"""Single protected execution path shared by APIs and AI agents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from time import monotonic, sleep
from typing import Any, Callable, Protocol
from uuid import uuid4

from fastapi import Depends

from app.config import get_settings
from app.redis_client import (
    IdempotencyState,
    RedisIdempotencyStore,
    get_idempotency_store,
)
from app.rules.engine import WAFRuleEngine, get_waf_engine
from app.rules.models import WAFDecision, WAFRequest
from app.schemas.tool_calls import ToolCallRequest
from app.services.audit import AuditRepository, get_audit_repository
from app.services.idempotency import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyUnavailableError,
)
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
        idempotency_store: RedisIdempotencyStore | None = None,
        idempotency_wait_timeout_seconds: float = 30,
        clock: Callable[[], float] = monotonic,
        wait_clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        request_id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._waf = waf
        self._gateway = gateway
        self._audit = audit
        self._enforcement_mode = enforcement_mode
        self._idempotency_store = idempotency_store
        self._idempotency_wait_timeout_seconds = idempotency_wait_timeout_seconds
        self._clock = clock
        self._wait_clock = wait_clock
        self._sleeper = sleeper
        self._request_id_factory = request_id_factory

    def list_tools(self) -> list[dict[str, Any]]:
        return self._gateway.list_tools()

    def execute(
        self,
        request: ToolCallRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ProtectedToolOutcome:
        if idempotency_key is None:
            return self._execute_once(request)
        if self._idempotency_store is None:
            raise IdempotencyUnavailableError(
                "Idempotency requires Redis-backed persistence."
            )
        return self._execute_idempotent(request, idempotency_key)

    def _execute_idempotent(
        self,
        request: ToolCallRequest,
        idempotency_key: str,
    ) -> ProtectedToolOutcome:
        assert self._idempotency_store is not None
        fingerprint = _request_fingerprint(request)
        deadline = self._wait_clock() + self._idempotency_wait_timeout_seconds

        while True:
            record = self._idempotency_store.begin_request(
                idempotency_key,
                fingerprint,
            )
            if record.state is IdempotencyState.CONFLICT:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different request."
                )
            if record.state is IdempotencyState.COMPLETED:
                assert record.result is not None
                return _deserialize_outcome(record.result)
            if record.state is IdempotencyState.CLAIMED:
                try:
                    outcome = self._execute_once(request)
                    self._idempotency_store.complete_request(
                        idempotency_key,
                        fingerprint,
                        _serialize_outcome(outcome),
                    )
                    return outcome
                except Exception:
                    self._idempotency_store.release_request(
                        idempotency_key,
                        fingerprint,
                    )
                    raise

            if self._wait_clock() >= deadline:
                raise IdempotencyInProgressError(
                    "A matching idempotent request is still in progress."
                )
            self._sleeper(0.01)
            current = self._idempotency_store.get_request(
                idempotency_key,
                fingerprint,
            )
            if current is None:
                continue
            if current.state is IdempotencyState.CONFLICT:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different request."
                )
            if current.state is IdempotencyState.COMPLETED:
                assert current.result is not None
                return _deserialize_outcome(current.result)

    def _execute_once(self, request: ToolCallRequest) -> ProtectedToolOutcome:
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
            self._waf.record_failure(waf_request)
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
            self._waf.record_failure(waf_request)
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
    settings = get_settings()
    mode = EnforcementMode(settings.waf_enforcement_mode)
    return ProtectedToolService(
        waf,
        gateway,
        audit,
        enforcement_mode=mode,
        idempotency_store=(
            get_idempotency_store() if settings.persistence_enabled else None
        ),
        idempotency_wait_timeout_seconds=settings.idempotency_wait_timeout_seconds,
    )


def _request_fingerprint(request: ToolCallRequest) -> str:
    canonical = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize_outcome(outcome: ProtectedToolOutcome) -> str:
    return json.dumps(
        {
            "decision": outcome.decision.model_dump(mode="json"),
            "tool": outcome.tool,
            "result": outcome.result,
            "effective_decision": (
                outcome.effective_decision.value
                if outcome.effective_decision is not None
                else None
            ),
            "enforcement_mode": outcome.enforcement_mode.value,
            "request_id": outcome.request_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_outcome(value: str) -> ProtectedToolOutcome:
    payload = json.loads(value)
    effective_decision = payload.get("effective_decision")
    return ProtectedToolOutcome(
        decision=WAFDecision.model_validate(payload["decision"]),
        tool=str(payload["tool"]),
        result=payload.get("result"),
        effective_decision=(
            AuditDecision(effective_decision)
            if effective_decision is not None
            else None
        ),
        enforcement_mode=EnforcementMode(payload["enforcement_mode"]),
        request_id=payload.get("request_id"),
    )
