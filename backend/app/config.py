"""Application configuration loaded from the environment."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime settings.

    Values come from environment variables first and from the project-level
    ``.env`` file as a development fallback. Secrets are never defaulted here.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Agent WAF"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8_000
    cors_allowed_origins: str = ""
    cors_allow_credentials: bool = False
    persistence_enabled: bool = False
    database_url: SecretStr | None = None
    database_echo: bool = False
    database_pool_size: int = 5
    database_connect_timeout_seconds: int = 5
    database_create_tables: bool = True
    redis_url: SecretStr | None = None
    redis_key_prefix: str = "agent-waf"
    redis_socket_timeout_seconds: int = 5
    redis_state_ttl_seconds: int = 86_400
    idempotency_ttl_seconds: int = 3_600
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 30
    waf_enforcement_mode: Literal["ENFORCE", "SHADOW"] = "ENFORCE"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if logging.getLevelName(normalized) == f"Level {normalized}":
            raise ValueError(f"Unsupported LOG_LEVEL: {value}")
        return normalized

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        return normalized

    @field_validator(
        "database_pool_size",
        "database_connect_timeout_seconds",
        "redis_socket_timeout_seconds",
        "redis_state_ttl_seconds",
        "idempotency_ttl_seconds",
        "openai_timeout_seconds",
        "port",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Timeout, pool, and TTL values must be positive")
        return value

    @field_validator("redis_key_prefix")
    @classmethod
    def validate_redis_key_prefix(cls, value: str) -> str:
        normalized = value.strip().strip(":")
        if not normalized:
            raise ValueError("REDIS_KEY_PREFIX cannot be empty")
        return normalized

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("HOST cannot be empty")
        return normalized

    @field_validator("port")
    @classmethod
    def validate_port_range(cls, value: int) -> int:
        if value > 65_535:
            raise ValueError("PORT must be at most 65535")
        return value

    @field_validator("openai_model")
    @classmethod
    def validate_openai_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("OPENAI_MODEL cannot be empty")
        return normalized

    @field_validator("waf_enforcement_mode", mode="before")
    @classmethod
    def normalize_enforcement_mode(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_persistence_urls(self) -> Self:
        if self.persistence_enabled:
            missing = []
            if self.database_url is None:
                missing.append("DATABASE_URL")
            if self.redis_url is None:
                missing.append("REDIS_URL")
            if missing:
                raise ValueError(
                    "Persistence is enabled but required settings are missing: "
                    + ", ".join(missing)
                )
        if self.cors_allow_credentials and "*" in self.allowed_cors_origins:
            raise ValueError(
                "CORS_ALLOW_CREDENTIALS cannot be enabled with a wildcard origin"
            )
        return self

    @property
    def allowed_cors_origins(self) -> tuple[str, ...]:
        return tuple(
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
