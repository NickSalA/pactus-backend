"""Persistence models for notification preferences and rules."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlmodel import Field

from ....core.domain.base import BaseTable


class NotificationRuleTable(BaseTable, table=True):
    """Stores organization-level and document-level due-date notification rules."""

    __tablename__ = "notification_rules"

    organization_id: int = Field(sa_column=Column("organization_id", Integer, ForeignKey("organizations.id"), nullable=False, index=True))
    document_id: int | None = Field(
        default=None,
        sa_column=Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    days_before_due: int = Field(sa_column=Column("days_before_due", Integer, nullable=False))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, default=True))
    created_by: int | None = Field(
        default=None,
        sa_column=Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
