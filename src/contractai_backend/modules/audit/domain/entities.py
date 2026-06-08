"""Persistent entities for audit tables."""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from contractai_backend.core.domain.base import BaseTable
from contractai_backend.core.domain.db_schemas import AUDIT_SCHEMA, IDENTITY_SCHEMA

from .value_objs import AuditUserAction


class UserActivityTable(BaseTable, table=True):
    """Audit trail for organization user management actions."""

    __tablename__ = "user_activity"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}

    id: int | None = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(always=False), primary_key=True, index=True),
    )
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    actor_name: str | None = Field(default=None, sa_column=Column("actor_name", String, nullable=True))
    actor_role: str = Field(sa_column=Column("actor_role", String, nullable=False))
    action: AuditUserAction = Field(
        sa_column=Column(
            "action",
            ENUM(AuditUserAction, name="audit_user_action", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    target_user_id: int | None = Field(
        default=None,
        sa_column=Column(
            "target_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    target_user_email: str | None = Field(default=None, sa_column=Column("target_user_email", String, nullable=True))
    target_user_name: str | None = Field(default=None, sa_column=Column("target_user_name", String, nullable=True))
    previous_role: str | None = Field(default=None, sa_column=Column("previous_role", String, nullable=True))
    role: str | None = Field(default=None, sa_column=Column("role", String, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
