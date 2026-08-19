"""WAF rule orchestration and default Phase 3 wiring."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from app.config import get_settings
from app.db.database import get_database
from app.db.repositories import PostgresPolicyRepository
from app.logging_config import get_logger
from app.redis_client import get_redis_client
from app.rules.base import WAFRule
from app.rules.data_scope import DataScopeRule
from app.rules.models import RuleDecision, WAFDecision, WAFRequest
from app.rules.parameter_validation import ParameterValidationRule
from app.rules.rate_limit import RateLimit, RateLimitRule
from app.rules.redis_stores import RedisRateLimitStore, RedisSequenceStateStore
from app.rules.sequence import SequenceEnforcementRule
from app.rules.stores import (
    InMemoryAgentScopeStore,
    InMemoryRateLimitStore,
    InMemorySequenceStateStore,
)

logger = get_logger(__name__)


class WAFRuleEngine:
    """Run rules in order and stop at the first blocking decision."""

    def __init__(self, rules: Iterable[WAFRule]) -> None:
        self._rules = tuple(rules)

    @property
    def rules(self) -> tuple[WAFRule, ...]:
        return self._rules

    def evaluate(self, request: WAFRequest) -> WAFDecision:
        results = []
        for rule in self._rules:
            result = rule.evaluate(request)
            results.append(result)
            if result.decision is RuleDecision.BLOCK:
                logger.info(
                    "WAF blocked call: agent_id=%s session_id=%s tool=%s rule=%s",
                    request.agent_id,
                    request.session_id,
                    request.tool,
                    result.rule,
                )
                return WAFDecision(
                    decision=RuleDecision.BLOCK,
                    results=results,
                    blocked_by=result,
                )

        return WAFDecision(decision=RuleDecision.ALLOW, results=results)

    def record_success(self, request: WAFRequest) -> None:
        """Let stateful rules record a successfully executed tool call."""
        for rule in self._rules:
            rule.record_success(request)

    def record_failure(self, request: WAFRequest) -> None:
        """Let stateful rules release reservations for unsuccessful calls."""
        for rule in self._rules:
            rule.record_failure(request)


def build_default_waf_engine() -> WAFRuleEngine:
    """Build the in-memory Phase 3 policy configuration."""
    rate_store = InMemoryRateLimitStore()
    scope_store = InMemoryAgentScopeStore(
        {"scoped-agent": {"c-001", "c-002"}}
    )
    sequence_store = InMemorySequenceStateStore()

    return WAFRuleEngine(
        [
            ParameterValidationRule(),
            DataScopeRule(scope_store),
            SequenceEnforcementRule([], sequence_store),
            RateLimitRule(
                {"search_products": RateLimit(max_calls=3, window_seconds=60)},
                rate_store,
            ),
        ]
    )


def build_persistent_waf_engine() -> WAFRuleEngine:
    """Build rules backed by PostgreSQL policy data and Redis runtime state."""
    settings = get_settings()
    database = get_database()
    redis_client = get_redis_client()
    policies = PostgresPolicyRepository(database.session_factory)
    configured_limits = policies.get_rate_limits()
    limits = {
        policy.tool_name: RateLimit(
            max_calls=policy.max_calls,
            window_seconds=policy.window_seconds,
        )
        for policy in configured_limits
    }

    return WAFRuleEngine(
        [
            ParameterValidationRule(),
            DataScopeRule(policies),
            SequenceEnforcementRule(
                policies.get_required_sequences(),
                RedisSequenceStateStore(
                    redis_client,
                    ttl_seconds=settings.redis_state_ttl_seconds,
                ),
            ),
            RateLimitRule(
                limits,
                RedisRateLimitStore(
                    redis_client,
                    ttl_seconds=settings.redis_state_ttl_seconds,
                ),
            ),
        ]
    )


@lru_cache
def get_waf_engine() -> WAFRuleEngine:
    """Return the configured process-wide WAF engine."""
    if get_settings().persistence_enabled:
        return build_persistent_waf_engine()
    return build_default_waf_engine()
