"""Persistence tests that require neither PostgreSQL nor Redis services."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.config import Settings
from app.db.database import Database
from app.db.models import Agent, AuditLog, Base, Policy, RegisteredTool
from app.db.repositories import PostgresAuditRepository, PostgresPolicyRepository
from app.redis_client import (
    IdempotencyState,
    RedisClient,
    RedisIdempotencyStore,
)
from app.rules.redis_stores import RedisRateLimitStore, RedisSequenceStateStore


@pytest.fixture
def database() -> Database:
    manager = Database("sqlite+pysqlite:///:memory:")
    manager.create_schema()
    yield manager
    manager.dispose()


def test_all_persistent_tables_are_declared() -> None:
    assert set(Base.metadata.tables) == {
        "agents",
        "tools",
        "policies",
        "audit_logs",
    }


def test_database_health_check(database: Database) -> None:
    database.check_connection()


def test_policy_repository_loads_agent_scope_from_database(
    database: Database,
) -> None:
    with database.session_factory() as session:
        session.add(Agent(id="agent-1", name="Test agent"))
        session.add(
            Policy(
                name="agent-1-customer-scope",
                agent_id="agent-1",
                customer_ids=["C001", "C002"],
            )
        )
        session.commit()

    repository = PostgresPolicyRepository(database.session_factory)

    assert repository.get_customer_ids("agent-1") == frozenset({"C001", "C002"})
    assert repository.get_customer_ids("unknown-agent") is None


def test_policy_repository_loads_rate_and_sequence_configuration(
    database: Database,
) -> None:
    with database.session_factory() as session:
        session.add(
            RegisteredTool(name="search_products", description="Search products")
        )
        session.add_all(
            [
                Policy(
                    name="search-rate",
                    tool_name="search_products",
                    rate_limit_max_calls=3,
                    rate_limit_window_seconds=60,
                ),
                Policy(
                    name="order-sequence",
                    required_sequence=[
                        "authenticate",
                        "get_customer",
                        "create_order",
                    ],
                ),
            ]
        )
        session.commit()

    repository = PostgresPolicyRepository(database.session_factory)

    assert repository.get_rate_limits()[0].tool_name == "search_products"
    assert repository.get_rate_limits()[0].max_calls == 3
    assert repository.get_required_sequences() == [
        ("authenticate", "get_customer", "create_order")
    ]


def test_audit_repository_persists_only_supplied_context(database: Database) -> None:
    repository = PostgresAuditRepository(database.session_factory)

    repository.record(
        agent_id="agent-1",
        session_id="session-1",
        tool_name="get_customer",
        decision="BLOCK",
        rule="data_scope",
        reason="Customer is outside agent scope",
        context={"request_id": "req-1"},
        request_id="req-1",
        sanitized_parameters={"customer_id": "C999", "token": "***MASKED***"},
        rules_evaluated=[
            {
                "rule": "data_scope",
                "decision": "BLOCK",
                "reason": "Customer is outside agent scope",
            }
        ],
        enforcement_mode="ENFORCE",
        latency_ms=4.25,
    )

    with database.session_factory() as session:
        record = session.scalar(select(AuditLog))
        assert record is not None
        assert record.decision == "BLOCK"
        assert record.rule == "data_scope"
        assert record.context == {"request_id": "req-1"}
        assert record.request_id == "req-1"
        assert record.sanitized_parameters["token"] == "***MASKED***"
        assert record.rules_evaluated[0]["rule"] == "data_scope"
        assert record.enforcement_mode == "ENFORCE"
        assert record.latency_ms == pytest.approx(4.25)

    events, total = repository.list_events(offset=0, limit=10)
    assert total == 1
    assert events[0]["request_id"] == "req-1"
    assert repository.metrics() == {
        "total_requests": 1,
        "allowed": 0,
        "blocked": 1,
        "would_block": 0,
    }


def test_persistence_requires_connection_urls() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(persistence_enabled=True)

    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message


def test_readiness_fails_when_startup_dependency_check_failed(
    client: TestClient, api_prefix: str
) -> None:
    client.app.state.persistence_ready = False

    try:
        response = client.get(f"{api_prefix}/ready")
    finally:
        client.app.state.persistence_ready = True

    assert response.status_code == 503
    assert response.json()["message"] == "Persistence dependencies are unavailable."


def redis_manager(client: Mock) -> RedisClient:
    manager = Mock()
    manager.client = client
    manager.key_prefix = "test-waf"
    return manager


def test_redis_rate_limit_store_uses_sorted_set_pipeline() -> None:
    client = Mock()
    pipeline = client.pipeline.return_value
    pipeline.execute.return_value = [0, 2, True]
    store = RedisRateLimitStore(redis_manager(client), ttl_seconds=120)

    count = store.count_since("agent-1\x1fsearch_products", 100.0)

    assert count == 2
    pipeline.zremrangebyscore.assert_called_once()
    pipeline.zcount.assert_called_once()
    pipeline.expire.assert_called_once()


def test_redis_rate_limit_reservation_uses_atomic_lua_script() -> None:
    client = Mock()
    client.eval.return_value = 1
    store = RedisRateLimitStore(redis_manager(client), ttl_seconds=120)

    reserved = store.reserve(
        "agent-1\x1fsearch_products",
        "reservation-1",
        160.0,
        max_calls=3,
        window_seconds=60,
    )

    assert reserved is True
    script, key_count, redis_key, *arguments = client.eval.call_args.args
    assert 'redis.call("ZCARD", key)' in script
    assert 'redis.call("ZADD", key, now, reservation_id)' in script
    assert key_count == 1
    assert redis_key.startswith("test-waf:rate-limit:")
    assert arguments == [160.0, 100.0, 3, "reservation-1", 120]


def test_redis_sequence_store_reads_and_appends_session_history() -> None:
    client = Mock()
    client.lrange.return_value = ["authenticate", "get_customer"]
    pipeline = client.pipeline.return_value
    store = RedisSequenceStateStore(redis_manager(client), ttl_seconds=600)

    history = store.get_completed_tools("agent-1", "session-1")
    store.record_completed_tool("agent-1", "session-1", "create_order")

    assert history == ("authenticate", "get_customer")
    pipeline.rpush.assert_called_once()
    pipeline.expire.assert_called_once()
    pipeline.execute.assert_called_once()


def test_idempotency_store_claims_hashed_namespaced_key() -> None:
    client = Mock()
    client.set.return_value = True
    store = RedisIdempotencyStore(
        redis_manager(client),
        ttl_seconds=300,
    )

    assert store.claim("secret-client-key") is True

    redis_key = client.set.call_args.args[0]
    assert redis_key.startswith("test-waf:idempotency:")
    assert "secret-client-key" not in redis_key
    assert client.set.call_args.kwargs == {
        "nx": True,
        "ex": 300,
    }


def test_idempotency_request_claim_uses_atomic_lua_state_machine() -> None:
    client = Mock()
    client.eval.return_value = ["CLAIMED", ""]
    store = RedisIdempotencyStore(
        redis_manager(client),
        ttl_seconds=300,
    )

    record = store.begin_request("secret-client-key", "fingerprint-1")

    assert record.state is IdempotencyState.CLAIMED
    script, key_count, redis_key, fingerprint, ttl = client.eval.call_args.args
    assert 'redis.call("HSET", key' in script
    assert key_count == 1
    assert redis_key.startswith("test-waf:idempotency:")
    assert "secret-client-key" not in redis_key
    assert fingerprint == "fingerprint-1"
    assert ttl == 300
