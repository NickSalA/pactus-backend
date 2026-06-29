"""Document entity for the documents domain."""

from datetime import UTC, date, datetime
from typing import Any, ClassVar

from pydantic import ValidationInfo, field_validator
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import APP_TYPES_SCHEMA, CONTRACTS_SCHEMA, IDENTITY_SCHEMA
from .value_objs import DocumentState


class DocumentTable(BaseTable, table=True):
    """Represents a stored contract document."""

    __tablename__: str = "documents"
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
    type: str | None = Field(default=None, sa_column=Column("type", String(255), nullable=True, index=True))
    start_date: date | None = Field(default=None, sa_column=Column("start_date", Date, nullable=True))
    end_date: date | None = Field(default=None, sa_column=Column("end_date", Date, nullable=True))
    form_data: dict[str, Any] | None = Field(default_factory=dict, sa_column=Column("form_data", JSONB, nullable=True))
    state: DocumentState | None = Field(
        default=None,
        sa_column=Column(
            "state",
            ENUM(DocumentState, name="document_state", schema=APP_TYPES_SCHEMA, create_type=False),
            nullable=True,
        ),
    )
    file_path: str | None = Field(default=None, sa_column=Column("file_path", Text, nullable=True))
    file_name: str | None = Field(default=None, sa_column=Column("file_name", Text, nullable=True))
    folder_id: int | None = Field(
        default=None,
        sa_column=Column(
            "folder_id",
            Integer,
            ForeignKey(f"{CONTRACTS_SCHEMA}.document_folders.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        """Rejects blank type values while allowing nulls during draft imports."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, end_date: date | None, info: ValidationInfo) -> date | None:
        """Ensures end date is not before start date."""
        if end_date is None:
            return None
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return end_date

    @field_validator("form_data")
    @classmethod
    def validate_form_data(cls, form_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Ensures form data stays as a JSON object when present."""
        if form_data is None:
            return None
        if not isinstance(form_data, dict):
            raise ValueError("form_data must be a JSON object.")
        return form_data
