"""Redis adapters for stateful WAF rule storage protocols."""

from __future__ import annotations

import hashlib
import uuid

from app.redis_client import RedisClient


class RedisRateLimitStore:
    """Sliding-window timestamps persisted in Redis sorted sets."""

    def __init__(
        self,
        redis_client: RedisClient,
        *,
        ttl_seconds: int,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def count_since(self, key: str, since: float) -> int:
        redis_key = self._key(key)
        pipeline = self._redis.client.pipeline(transaction=True)
        pipeline.zremrangebyscore(redis_key, "-inf", f"({since}")
        pipeline.zcount(redis_key, since, "+inf")
        pipeline.expire(redis_key, self._ttl_seconds)
        _, count, _ = pipeline.execute()
        return int(count)

    def add(self, key: str, timestamp: float) -> None:
        redis_key = self._key(key)
        member = f"{timestamp}:{uuid.uuid4().hex}"
        pipeline = self._redis.client.pipeline(transaction=True)
        pipeline.zadd(redis_key, {member: timestamp})
        pipeline.expire(redis_key, self._ttl_seconds)
        pipeline.execute()

    def _key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{self._redis.key_prefix}:rate-limit:{digest}"


class RedisSequenceStateStore:
    """Successful session history persisted in Redis lists."""

    def __init__(
        self,
        redis_client: RedisClient,
        *,
        ttl_seconds: int,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def get_completed_tools(self, agent_id: str, session_id: str) -> tuple[str, ...]:
        values = self._redis.client.lrange(self._key(agent_id, session_id), 0, -1)
        return tuple(str(value) for value in values)

    def record_completed_tool(
        self, agent_id: str, session_id: str, tool: str
    ) -> None:
        key = self._key(agent_id, session_id)
        pipeline = self._redis.client.pipeline(transaction=True)
        pipeline.rpush(key, tool)
        pipeline.expire(key, self._ttl_seconds)
        pipeline.execute()

    def _key(self, agent_id: str, session_id: str) -> str:
        digest = hashlib.sha256(
            f"{agent_id}\x1f{session_id}".encode("utf-8")
        ).hexdigest()
        return f"{self._redis.key_prefix}:sequence:{digest}"
