"""SQLAlchemy 2.0 ORM models for the SGM Telegram Signal Copier database."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    subscription_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="free"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    telegram_sessions: Mapped[list[TelegramSessionModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    routing_rules: Mapped[list[RoutingRuleModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    signal_logs: Mapped[list[SignalLogModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class TelegramSessionModel(Base):
    __tablename__ = "telegram_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "phone_number", name="uq_session_user_phone"),
        Index("idx_telegram_sessions_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    session_string_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true"
    )
    last_active: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship(back_populates="telegram_sessions")


class RoutingRuleModel(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        CheckConstraint(
            "payload_version IN ('V1', 'V2')",
            name="ck_routing_rules_payload_version",
        ),
        Index(
            "idx_routing_rules_lookup",
            "user_id",
            "source_channel_id",
            postgresql_where="is_active = TRUE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_channel_id: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    source_channel_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    destination_webhook_url: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    payload_version: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    symbol_mappings: Mapped[dict] = mapped_column(
        JSONB, server_default="{}"
    )
    risk_overrides: Mapped[dict] = mapped_column(
        JSONB, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship(back_populates="routing_rules")
    signal_logs: Mapped[list[SignalLogModel]] = relationship(
        back_populates="routing_rule"
    )


class SignalLogModel(Base):
    __tablename__ = "signal_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'ignored')",
            name="ck_signal_logs_status",
        ),
        Index("idx_signal_logs_user_date", "user_id", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    routing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routing_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_message: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    parsed_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    webhook_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship(back_populates="signal_logs")
    routing_rule: Mapped[RoutingRuleModel | None] = relationship(
        back_populates="signal_logs"
    )
