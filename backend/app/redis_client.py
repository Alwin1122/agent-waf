"""Redis connection management and idempotency-key storage."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from redis import Redis

from app.config import get_settings


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

    def _key(self, idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return f"{self._redis.key_prefix}:idempotency:{digest}"


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
