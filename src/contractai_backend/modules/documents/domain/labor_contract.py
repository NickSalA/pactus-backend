"""Labor contract entity for worker-specific document data."""

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import field_validator
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import APP_TYPES_SCHEMA, CONTRACTS_SCHEMA
from .value_objs import CurrencyType


class LaborContractTable(BaseTable, table=True):
    """Represents labor-specific data for a document."""

    __tablename__: str = "labor_contracts"
    __table_args__: ClassVar[dict[str, str]] = {"schema": CONTRACTS_SCHEMA}

    document_id: int = Field(
        sa_column=Column(
            "document_id",
            Integer,
            ForeignKey(f"{CONTRACTS_SCHEMA}.documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )
    )
    worker_name: str | None = Field(default=None, sa_column=Column("worker_name", String(255), nullable=True, index=True))
    worker_document_number: str | None = Field(default=None, sa_column=Column("worker_document_number", String(255), nullable=True))
    position: str | None = Field(default=None, sa_column=Column("position", String(255), nullable=True))
    salary_value: float | None = Field(default=None, sa_column=Column("salary_value", Float, nullable=True))
    salary_currency: CurrencyType | None = Field(
        default=None,
        sa_column=Column(
            "salary_currency",
            ENUM(CurrencyType, name="currency_type", schema=APP_TYPES_SCHEMA, create_type=False),
            nullable=True,
        ),
    )
    salary_periodicity: str | None = Field(default=None, sa_column=Column("salary_periodicity", String(255), nullable=True))
    contract_modality: str | None = Field(default=None, sa_column=Column("contract_modality", String(255), nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    @field_validator("worker_name", "worker_document_number", "position", "salary_periodicity", "contract_modality")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")

    @field_validator("salary_value")
    @classmethod
    def validate_salary_value(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("Salary value must be a positive number.")
        return value
