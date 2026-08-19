"""Redis connection management and idempotency-key storage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from redis import Redis

from app.config import get_settings

IDEMPOTENCY_BEGIN_SCRIPT = """
local key = KEYS[1]
local fingerprint = ARGV[1]
local ttl_seconds = tonumber(ARGV[2])

if redis.call("EXISTS", key) == 0 then
    redis.call("HSET", key, "fingerprint", fingerprint, "state", "RUNNING")
    redis.call("EXPIRE", key, ttl_seconds)
    return {"CLAIMED", ""}
end

local existing_fingerprint = redis.call("HGET", key, "fingerprint")
if existing_fingerprint ~= fingerprint then
    return {"CONFLICT", ""}
end

local state = redis.call("HGET", key, "state") or "RUNNING"
local result = redis.call("HGET", key, "result") or ""
return {state, result}
"""

IDEMPOTENCY_COMPLETE_SCRIPT = """
local key = KEYS[1]
local fingerprint = ARGV[1]
local result = ARGV[2]
local ttl_seconds = tonumber(ARGV[3])

if redis.call("HGET", key, "fingerprint") ~= fingerprint then
    return 0
end
redis.call("HSET", key, "state", "COMPLETED", "result", result)
redis.call("EXPIRE", key, ttl_seconds)
return 1
"""

IDEMPOTENCY_RELEASE_SCRIPT = """
local key = KEYS[1]
local fingerprint = ARGV[1]

if redis.call("HGET", key, "fingerprint") == fingerprint
    and redis.call("HGET", key, "state") == "RUNNING" then
    return redis.call("DEL", key)
end
return 0
"""


class IdempotencyState(str, Enum):
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class IdempotencyRecord:
    state: IdempotencyState
    result: str | None = None


class RedisClient:
    """Own a Redis connection pool and namespaced utility operations."""

    def __init__(
        self,
        url: str,
        *,
        key_prefix: str,
        socket_timeout_seconds: int = 5,
    ) -> None:
        self.client: Redis = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=socket_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
            health_check_interval=30,
        )
        self.key_prefix = key_prefix

    def check_connection(self) -> None:
        self.client.ping()

    def close(self) -> None:
        self.client.close()


class RedisIdempotencyStore:
    """Claim and resolve idempotency keys with bounded retention."""

    def __init__(
        self,
        redis_client: RedisClient,
        *,
        ttl_seconds: int,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def claim(self, idempotency_key: str, value: str = "processing") -> bool:
        """Atomically claim a key; return false when it already exists."""
        result = self._redis.client.set(
            self._key(idempotency_key),
            value,
            nx=True,
            ex=self._ttl_seconds,
        )
        return bool(result)

    def get(self, idempotency_key: str) -> str | None:
        value = self._redis.client.get(self._key(idempotency_key))
        return str(value) if value is not None else None

    def complete(self, idempotency_key: str, value: str) -> None:
        self._redis.client.set(
            self._key(idempotency_key),
            value,
            ex=self._ttl_seconds,
        )

    def begin_request(
        self, idempotency_key: str, fingerprint: str
    ) -> IdempotencyRecord:
        """Atomically claim a request or inspect its existing state."""
        state, result = self._redis.client.eval(
            IDEMPOTENCY_BEGIN_SCRIPT,
            1,
            self._request_key(idempotency_key),
            fingerprint,
            self._ttl_seconds,
        )
        return IdempotencyRecord(
            state=IdempotencyState(str(state)),
            result=str(result) if result else None,
        )

    def get_request(
        self, idempotency_key: str, fingerprint: str
    ) -> IdempotencyRecord | None:
        """Read the current state while rejecting payload-key conflicts."""
        values = self._redis.client.hmget(
            self._request_key(idempotency_key),
            "fingerprint",
            "state",
            "result",
        )
        existing_fingerprint, state, result = values
        if existing_fingerprint is None:
            return None
        if str(existing_fingerprint) != fingerprint:
            return IdempotencyRecord(IdempotencyState.CONFLICT)
        return IdempotencyRecord(
            state=IdempotencyState(str(state)),
            result=str(result) if result else None,
        )

    def complete_request(
        self,
        idempotency_key: str,
        fingerprint: str,
        result: str,
    ) -> None:
        """Publish the completed response only for the matching claim."""
        completed = self._redis.client.eval(
            IDEMPOTENCY_COMPLETE_SCRIPT,
            1,
            self._request_key(idempotency_key),
            fingerprint,
            result,
            self._ttl_seconds,
        )
        if not completed:
            raise RuntimeError("Idempotency claim was lost before completion")

    def release_request(self, idempotency_key: str, fingerprint: str) -> None:
        """Release a failed in-flight request so a retry may execute it."""
        self._redis.client.eval(
            IDEMPOTENCY_RELEASE_SCRIPT,
            1,
            self._request_key(idempotency_key),
            fingerprint,
        )

    def _key(self, idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return f"{self._redis.key_prefix}:idempotency:{digest}"

    def _request_key(self, idempotency_key: str) -> str:
        return f"{self._key(idempotency_key)}:request"


@lru_cache
def get_redis_client() -> RedisClient:
    settings = get_settings()
    if settings.redis_url is None:
        raise RuntimeError("REDIS_URL is required for Redis access")
    return RedisClient(
        settings.redis_url.get_secret_value(),
        key_prefix=settings.redis_key_prefix,
        socket_timeout_seconds=settings.redis_socket_timeout_seconds,
    )


@lru_cache
def get_idempotency_store() -> RedisIdempotencyStore:
    settings = get_settings()
    return RedisIdempotencyStore(
        get_redis_client(),
        ttl_seconds=settings.idempotency_ttl_seconds,
    )
