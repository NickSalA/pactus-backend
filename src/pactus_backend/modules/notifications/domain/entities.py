"""Persistence models for notification preferences and rules."""

from datetime import UTC, date, datetime
from typing import ClassVar

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import CONTRACTS_SCHEMA, IDENTITY_SCHEMA, NOTIFICATIONS_SCHEMA


class NotificationSendLog(BaseTable, table=True):
    """Tracks daily email sends per organization to prevent duplicate sends on the same day."""

    __tablename__ = "notification_send_logs"
    __table_args__: ClassVar[tuple[UniqueConstraint, dict[str, str]]] = (
        UniqueConstraint("organization_id", "sent_date", name="uq_notification_send_log_org_date"),
        {"schema": NOTIFICATIONS_SCHEMA},
    )

    organization_id: int = Field(
        sa_column=Column("organization_id", Integer, ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id"), nullable=False, index=True)
    )
    sent_date: date = Field(sa_column=Column("sent_date", Date, nullable=False))
    emails_sent: int = Field(default=0, sa_column=Column("emails_sent", Integer, nullable=False, default=0))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )


class NotificationRuleTable(BaseTable, table=True):
    """Stores organization-level and document-level due-date notification rules."""

    __tablename__ = "notification_rules"
    __table_args__: ClassVar[dict[str, str]] = {"schema": NOTIFICATIONS_SCHEMA}

    organization_id: int = Field(
        sa_column=Column("organization_id", Integer, ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id"), nullable=False, index=True)
    )
    document_id: int | None = Field(
        default=None,
        sa_column=Column(
            "document_id",
            Integer,
            ForeignKey(f"{CONTRACTS_SCHEMA}.documents.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    days_before_due: int = Field(sa_column=Column("days_before_due", Integer, nullable=False))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, default=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
