"""Service entity for the services module."""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import field_validator
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import CATALOG_SCHEMA, IDENTITY_SCHEMA


class ServiceTable(BaseTable, table=True):
    """Represents a service available for contracts."""

    __tablename__: str = "services"
    __table_args__: ClassVar[dict[str, str]] = {"schema": CATALOG_SCHEMA}

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
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Service name cannot be empty.")
