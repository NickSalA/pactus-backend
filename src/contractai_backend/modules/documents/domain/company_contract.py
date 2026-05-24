"""Company contract entity for company-specific document data."""

from datetime import UTC, datetime

from pydantic import field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlmodel import Field

from ....core.domain.base import BaseTable


class CompanyContractTable(BaseTable, table=True):
    """Represents company-specific data for a document."""

    __tablename__: str = "company_contracts"

    document_id: int = Field(sa_column=Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True))
    ruc: str | None = Field(default=None, sa_column=Column("ruc", String(255), nullable=True))
    client: str | None = Field(default=None, sa_column=Column("client", String(255), nullable=True, index=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    @field_validator("ruc", "client")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")
