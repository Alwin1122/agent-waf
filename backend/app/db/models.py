"""SQLAlchemy models for persistent Agent WAF configuration and audit data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base shared by all database models."""


class Agent(Base):
    """An AI agent known to the WAF."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    policies: Mapped[list[Policy]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class RegisteredTool(Base):
    """Persistent metadata for a tool exposed by the gateway."""

    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    policies: Mapped[list[Policy]] = relationship(back_populates="tool")


class Policy(Base):
    """WAF policy configuration, optionally scoped to an agent and tool."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str | None] = mapped_column(
        ForeignKey("tools.name", ondelete="CASCADE"), index=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    customer_ids: Mapped[list[str] | None] = mapped_column(JSON)
    rate_limit_max_calls: Mapped[int | None] = mapped_column(Integer)
    rate_limit_window_seconds: Mapped[int | None] = mapped_column(Integer)
    required_sequence: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    agent: Mapped[Agent | None] = relationship(back_populates="policies")
    tool: Mapped[RegisteredTool | None] = relationship(back_populates="policies")


class AuditLog(Base):
    """Immutable record of a WAF decision and optional tool execution."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_agent_created", "agent_id", "created_at"),
        Index("ix_audit_logs_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(64), index=True
    )
    agent_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    rule: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    rules_evaluated: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    enforcement_mode: Mapped[str | None] = mapped_column(String(16))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    context: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
