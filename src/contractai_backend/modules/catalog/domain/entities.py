"""Service entity for the services module."""

from datetime import UTC, datetime

from pydantic import field_validator
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field

from ....core.domain.base import BaseTable


class ServiceTable(BaseTable, table=True):
    """Represents a service available for contracts."""

    __tablename__: str = "services"

    organization_id: int = Field(sa_column=Column("organization_id", Integer, ForeignKey("organizations.id"), nullable=False, index=True))
    name: str = Field(sa_column=Column("name", String(255), nullable=False))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, default=True))
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
        """Rejects blank service names."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Service name cannot be empty.")
        return cleaned
