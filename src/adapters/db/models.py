"""SQLAlchemy 2.0 ORM models for the SGM Telegram Signal Copier database."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false as sa_false,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID
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
    notification_preferences: Mapped[dict] = mapped_column(
        JSONB, server_default='{}', nullable=False
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_false(), nullable=False
    )
    is_disabled: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_false(), nullable=False
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_false(), nullable=False
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_tos_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    accepted_risk_waiver: Mapped[bool] = mapped_column(
        Boolean, server_default=sa_false(), nullable=False
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
        Index("idx_telegram_sessions_user_active", "user_id", "is_active"),
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
    disconnected_reason: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        Index("idx_routing_rules_user_created", "user_id", "created_at"),
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
    webhook_body_template: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    rule_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    destination_label: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    destination_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="sagemaster_forex"
    )
    custom_ai_instructions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    enabled_actions: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )
    keyword_blacklist: Mapped[list] = mapped_column(
        JSONB, server_default="[]", nullable=False
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
        Index("idx_signal_logs_channel_message", "channel_id", "message_id"),
        Index("idx_signal_logs_user_status_date", "user_id", "status", "processed_at"),
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
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    channel_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    reply_to_msg_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
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


class ParserConfigModel(Base):
    __tablename__ = "parser_config"
    __table_args__ = (
        Index("idx_parser_config_active", "is_active"),
        Index("idx_parser_config_key", "config_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_key: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    model_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    temperature: Mapped[float | None] = mapped_column(
        nullable=True
    )
    version: Mapped[int] = mapped_column(
        nullable=False, default=1
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true"
    )
    change_note: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    changed_by_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GlobalSettingModel(Base):
    __tablename__ = "global_settings"

    key: Mapped[str] = mapped_column(
        String(100), primary_key=True
    )
    value: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    token_lookup_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship()


class TermsAcceptanceLogModel(Base):
    """Audit trail for terms/privacy/risk waiver acceptance — fintech compliance."""

    __tablename__ = "terms_acceptance_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False  # 'tos', 'privacy', 'risk_waiver'
    )
    document_version: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserModel] = relationship()


class EmailVerificationTokenModel(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    token_lookup_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship()
