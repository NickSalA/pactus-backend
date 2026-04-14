"""Document-service link entity and related domain rules."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from pydantic import ValidationInfo, field_validator
from sqlalchemy import Column, Date, Float, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BaseTable
from .exceptions import DocumentValidationError
from .value_objs import CurrencyType


class ServiceWindowLike(Protocol):
    """Describes the fields needed for service window rules."""

    service_id: int
    currency: CurrencyType
    start_date: date
    end_date: date


def validate_service_currency_alignment(service_items: Sequence[ServiceWindowLike]) -> None:
    """Ensures all service items use the same currency."""
    currencies = {item.currency for item in service_items}
    if len(currencies) > 1:
        raise DocumentValidationError(message="Todos los servicios asociados al contrato deben usar la misma moneda.")


def validate_service_periods(
    document_start_date: date,
    document_end_date: date,
    service_items: Sequence[ServiceWindowLike],
) -> None:
    """Ensures service dates stay inside the document range."""
    for item in service_items:
        if item.start_date < document_start_date or item.end_date > document_end_date:
            raise DocumentValidationError(
                message=(
                    f"El servicio {item.service_id} debe tener fechas dentro del rango del contrato "
                    f"(contrato: {document_start_date.isoformat()} a {document_end_date.isoformat()}, "
                    f"servicio: {item.start_date.isoformat()} a {item.end_date.isoformat()})."
                )
            )


class DocumentServiceTable(BaseTable, table=True):
    """Represents a service attached to a document."""

    __tablename__: str = "documents_services"

    document_id: int = Field(sa_column=Column("document_id", Integer, nullable=False, index=True))
    service_id: int = Field(sa_column=Column("service_id", Integer, nullable=False, index=True))
    description: str | None = Field(default=None, sa_column=Column("description", Text, nullable=True))
    value: float = Field(sa_column=Column("value", Float, nullable=False))
    currency: CurrencyType = Field(sa_column=Column("currency", ENUM(CurrencyType, name="currency_type"), nullable=False))
    start_date: date = Field(sa_column=Column("start_date", Date, nullable=False))
    end_date: date = Field(sa_column=Column("end_date", Date, nullable=False))

    @field_validator("document_id", "service_id")
    @classmethod
    def validate_positive_ids(cls, value: int) -> int:
        """Requires positive identifiers."""
        if value <= 0:
            raise ValueError("ID must be a positive integer.")
        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: float) -> float:
        """Rejects negative service values."""
        if value < 0:
            raise ValueError("Value must be a positive number.")
        return value

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, end_date: date, info: ValidationInfo) -> date:
        """Ensures end date is not before start date."""
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return end_date
