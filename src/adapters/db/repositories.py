"""Concrete SQLAlchemy repository implementations.

These classes implement the repository protocols defined in
``src.core.interfaces`` and convert between SQLAlchemy ORM models
and Pydantic domain models from ``src.core.models``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import (
    RoutingRuleModel,
    SignalLogModel,
    UserModel,
)
from src.core.models import RoutingRule, User


# ---------------------------------------------------------------------------
# User repository
# ---------------------------------------------------------------------------


class SqlAlchemyUserRepository:
    """Async user repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def create(self, email: str, password_hash: str) -> User:
        db_user = UserModel(email=email, password_hash=password_hash)
        self._session.add(db_user)
        await self._session.flush()
        return self._to_domain(db_user)

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    # ------------------------------------------------------------------
    @staticmethod
    def _to_domain(row: UserModel) -> User:
        return User(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            subscription_tier=row.subscription_tier,
            created_at=row.created_at,
        )


# ---------------------------------------------------------------------------
# Routing-rule repository
# ---------------------------------------------------------------------------


class SqlAlchemyRoutingRuleRepository:
    """Async routing-rule repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_rules_for_channel(
        self, user_id: UUID, channel_id: str
    ) -> list[RoutingRule]:
        stmt = (
            select(RoutingRuleModel)
            .where(
                RoutingRuleModel.user_id == user_id,
                RoutingRuleModel.source_channel_id == channel_id,
                RoutingRuleModel.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(r) for r in result.scalars().all()]

    async def create(self, rule: RoutingRule) -> RoutingRule:
        db_rule = RoutingRuleModel(
            id=rule.id,
            user_id=rule.user_id,
            source_channel_id=rule.source_channel_id,
            source_channel_name=rule.source_channel_name,
            destination_webhook_url=rule.destination_webhook_url,
            payload_version=rule.payload_version,
            symbol_mappings=rule.symbol_mappings,
            risk_overrides=rule.risk_overrides,
            is_active=rule.is_active,
        )
        self._session.add(db_rule)
        await self._session.flush()
        return self._to_domain(db_rule)

    async def get_by_user(self, user_id: UUID) -> list[RoutingRule]:
        stmt = (
            select(RoutingRuleModel)
            .where(RoutingRuleModel.user_id == user_id)
            .order_by(RoutingRuleModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(r) for r in result.scalars().all()]

    async def count_by_user(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(RoutingRuleModel)
            .where(RoutingRuleModel.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, rule_id: UUID, user_id: UUID) -> RoutingRule | None:
        stmt = select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def update(self, rule_id: UUID, user_id: UUID, **fields) -> RoutingRule | None:
        stmt = select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return self._to_domain(row)

    async def delete(self, rule_id: UUID, user_id: UUID) -> bool:
        stmt = select(RoutingRuleModel).where(
            RoutingRuleModel.id == rule_id,
            RoutingRuleModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    # ------------------------------------------------------------------
    @staticmethod
    def _to_domain(row: RoutingRuleModel) -> RoutingRule:
        return RoutingRule(
            id=row.id,
            user_id=row.user_id,
            source_channel_id=row.source_channel_id,
            source_channel_name=row.source_channel_name,
            destination_webhook_url=row.destination_webhook_url,
            payload_version=row.payload_version,
            symbol_mappings=row.symbol_mappings or {},
            risk_overrides=row.risk_overrides or {},
            is_active=row.is_active,
        )


# ---------------------------------------------------------------------------
# Signal-log repository
# ---------------------------------------------------------------------------


class SqlAlchemySignalLogRepository:
    """Async signal-log repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        user_id: UUID,
        routing_rule_id: UUID | None,
        raw_message: str,
        parsed_data: dict | None,
        webhook_payload: dict | None,
        status: str,
        error_message: str | None = None,
    ) -> None:
        entry = SignalLogModel(
            user_id=user_id,
            routing_rule_id=routing_rule_id,
            raw_message=raw_message,
            parsed_data=parsed_data,
            webhook_payload=webhook_payload,
            status=status,
            error_message=error_message,
        )
        self._session.add(entry)
        await self._session.flush()

    async def get_by_user(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        stmt = (
            select(SignalLogModel)
            .where(SignalLogModel.user_id == user_id)
            .order_by(SignalLogModel.processed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "user_id": str(row.user_id),
                "routing_rule_id": str(row.routing_rule_id) if row.routing_rule_id else None,
                "raw_message": row.raw_message,
                "parsed_data": row.parsed_data,
                "webhook_payload": row.webhook_payload,
                "status": row.status,
                "error_message": row.error_message,
                "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            }
            for row in rows
        ]
