"""Folder entity for the folders module."""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import APP_TYPES_SCHEMA, CONTRACTS_SCHEMA, IDENTITY_SCHEMA
from ...users.domain.value_objs import UserRole


class FolderTable(BaseTable, table=True):
    """Represents a folder available for one organization and role group."""

    __tablename__ = "document_folders"
    __table_args__: ClassVar[dict[str, str]] = {"schema": CONTRACTS_SCHEMA}

    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            Integer,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    name: str = Field(sa_column=Column("name", String(255), nullable=False))
    owner_role: UserRole = Field(
        sa_column=Column(
            "owner_role",
            ENUM(UserRole, name="user_role", schema=APP_TYPES_SCHEMA, create_type=False),
            nullable=False,
        )
    )
    created_by: int = Field(
        sa_column=Column("created_by", Integer, ForeignKey(f"{IDENTITY_SCHEMA}.users.id"), nullable=False, index=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Rejects blank folder names."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Folder name cannot be empty.")
        return cleaned
