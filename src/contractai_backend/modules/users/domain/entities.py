"""Módulo de entidades para la gestión de usuarios."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import APP_TYPES_SCHEMA, IDENTITY_SCHEMA
from .value_objs import UserRole


class UserTable(BaseTable, table=True):
    __tablename__ = "users"
    __table_args__: ClassVar[dict[str, str]] = {"schema": IDENTITY_SCHEMA}

    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            Integer,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    supabase_user_id: UUID | None = Field(default=None, sa_column=Column("supabase_user_id", nullable=True, unique=True))
    email: str = Field(sa_column=Column("email", String(255), nullable=False, unique=True, index=True))
    full_name: str | None = Field(default=None, sa_column=Column("full_name", String(255), nullable=True))
    avatar_url: str | None = Field(default=None, sa_column=Column("avatar_url", Text, nullable=True))
    role: UserRole = Field(
        default=UserRole.WORKER,
        sa_column=Column("role", ENUM(UserRole, name="user_role", schema=APP_TYPES_SCHEMA, create_type=False), nullable=False),
    )
    receives_notifications: bool = Field(
        default=False,
        sa_column=Column("receives_notifications", Boolean, nullable=False, default=False),
    )
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, default=True))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC), sa_column=Column("created_at", DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC), sa_column=Column("updated_at", DateTime(timezone=True), nullable=False)
    )
