"""Folder entity for the folders module."""

from datetime import UTC, datetime

from pydantic import field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ...users.domain.value_objs import UserRole


class FolderTable(BaseTable, table=True):
    """Represents a folder available for one organization and role group."""

    __tablename__ = "document_folders"

    organization_id: int = Field(sa_column=Column("organization_id", Integer, ForeignKey("organizations.id"), nullable=False, index=True))
    name: str = Field(sa_column=Column("name", String(255), nullable=False))
    owner_role: UserRole = Field(sa_column=Column("owner_role", ENUM(UserRole, name="user_role", create_type=False), nullable=False))
    created_by: int = Field(sa_column=Column("created_by", Integer, ForeignKey("users.id"), nullable=False))
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
