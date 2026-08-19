"""PostgreSQL repositories used by WAF rules and audit services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Agent, AuditLog, Policy, RegisteredTool

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class RateLimitPolicy:
    tool_name: str
    max_calls: int
    window_seconds: int


class PostgresPolicyRepository:
    """Read policy and scope configuration from PostgreSQL."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def get_customer_ids(self, agent_id: str) -> frozenset[str] | None:
        with self._session_factory() as session:
            rows = session.scalars(
                select(Policy.customer_ids).where(
                    Policy.agent_id == agent_id,
                    Policy.is_enabled.is_(True),
                    Policy.customer_ids.is_not(None),
                )
            ).all()
        if not rows:
            return None
        return frozenset(
            customer_id
            for customer_ids in rows
            for customer_id in (customer_ids or [])
        )

    def get_rate_limits(self) -> list[RateLimitPolicy]:
        """Load enabled global rate limits.

        Agent-specific counters still remain isolated because the rule's Redis
        key includes the agent id.
        """
        with self._session_factory() as session:
            policies = session.scalars(
                select(Policy).where(
                    Policy.agent_id.is_(None),
                    Policy.tool_name.is_not(None),
                    Policy.is_enabled.is_(True),
                    Policy.rate_limit_max_calls.is_not(None),
                    Policy.rate_limit_window_seconds.is_not(None),
                )
            ).all()
        return [
            RateLimitPolicy(
                tool_name=policy.tool_name or "",
                max_calls=policy.rate_limit_max_calls or 1,
                window_seconds=policy.rate_limit_window_seconds or 1,
            )
            for policy in policies
        ]

    def get_required_sequences(self) -> list[tuple[str, ...]]:
        with self._session_factory() as session:
            sequences = session.scalars(
                select(Policy.required_sequence).where(
                    Policy.agent_id.is_(None),
                    Policy.is_enabled.is_(True),
                    Policy.required_sequence.is_not(None),
                )
            ).all()
        return [tuple(sequence) for sequence in sequences if sequence]


class PostgresAuditRepository:
    """Append immutable, non-sensitive audit records."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def record(
        self,
        *,
        agent_id: str,
        session_id: str,
        tool_name: str,
        decision: str,
        reason: str,
        rule: str | None = None,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
        sanitized_parameters: dict[str, Any] | None = None,
        rules_evaluated: list[dict[str, Any]] | None = None,
        enforcement_mode: str = "ENFORCE",
        latency_ms: float = 0.0,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                AuditLog(
                    agent_id=agent_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    decision=decision,
                    rule=rule,
                    reason=reason,
                    request_id=request_id,
                    sanitized_parameters=sanitized_parameters or {},
                    rules_evaluated=rules_evaluated or [],
                    enforcement_mode=enforcement_mode,
                    latency_ms=latency_ms,
                    context=context or {},
                )
            )
            session.commit()

    def list_events(
        self, *, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(AuditLog)) or 0
            events = session.scalars(
                select(AuditLog)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        return [_audit_to_dict(event) for event in events], int(total)

    def metrics(self) -> dict[str, int]:
        with self._session_factory() as session:
            counts = {
                decision: int(
                    session.scalar(
                        select(func.count())
                        .select_from(AuditLog)
                        .where(AuditLog.decision == decision)
                    )
                    or 0
                )
                for decision in ("ALLOW", "BLOCK", "WOULD_BLOCK")
            }
            total = int(session.scalar(select(func.count()).select_from(AuditLog)) or 0)
        return {
            "total_requests": total,
            "allowed": counts["ALLOW"],
            "blocked": counts["BLOCK"],
            "would_block": counts["WOULD_BLOCK"],
        }


def _audit_to_dict(event: AuditLog) -> dict[str, Any]:
    return {
        "timestamp": event.created_at,
        "request_id": event.request_id,
        "agent_id": event.agent_id,
        "session_id": event.session_id,
        "tool": event.tool_name,
        "sanitized_parameters": event.sanitized_parameters or {},
        "rules_evaluated": event.rules_evaluated or [],
        "decision": event.decision,
        "reason": event.reason,
        "enforcement_mode": event.enforcement_mode or "ENFORCE",
        "latency_ms": event.latency_ms or 0.0,
    }


def seed_core_records(
    session_factory: SessionFactory,
    tools: list[dict[str, Any]],
) -> None:
    """Idempotently register built-in tools and the default rate policy."""
    with session_factory() as session:
        for descriptor in tools:
            existing = session.get(RegisteredTool, descriptor["name"])
            if existing is None:
                session.add(
                    RegisteredTool(
                        name=descriptor["name"],
                        description=descriptor["description"],
                    )
                )

        default_policy = session.scalar(
            select(Policy).where(
                Policy.name == "default-search-products-rate-limit"
            )
        )
        if default_policy is None:
            session.add(
                Policy(
                    name="default-search-products-rate-limit",
                    tool_name="search_products",
                    rate_limit_max_calls=3,
                    rate_limit_window_seconds=60,
                )
            )
        session.commit()


def upsert_agent(
    session_factory: SessionFactory,
    agent_id: str,
    *,
    name: str | None = None,
) -> Agent:
    """Small repository helper for provisioning agents."""
    with session_factory() as session:
        agent = session.get(Agent, agent_id)
        if agent is None:
            agent = Agent(id=agent_id, name=name)
            session.add(agent)
        elif name is not None:
            agent.name = name
        session.commit()
        session.refresh(agent)
        return agent
