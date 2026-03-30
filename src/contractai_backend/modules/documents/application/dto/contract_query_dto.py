"""DTOs for structured contract queries."""

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator

from ...domain import CurrencyType, DocumentState, DocumentType

VALID_OPERATIONS = {"count", "list"}
VALID_DATE_MODES = {"overlap", "start_date", "end_date"}


class ContractQueryDTO(BaseModel):
    operation: str
    client: str | None = None
    contract_name: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    currency: CurrencyType | None = None
    state: DocumentState | None = None
    document_type: DocumentType | None = None
    period_start: date | None = None
    period_end: date | None = None
    date_mode: str = "overlap"
    limit: int | None = None

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        """Valida que la operación sea 'count' o 'list'."""
        normalized = value.strip().lower()
        if normalized not in VALID_OPERATIONS:
            raise ValueError("La operacion debe ser 'count' o 'list'.")
        return normalized

    @field_validator("client", "contract_name")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Valida que los campos de texto opcionales no sean solo espacios en blanco."""
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        """Normaliza el valor de moneda a mayúsculas y elimina espacios, o lo deja como None si es vacío."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("state", "document_type", mode="before")
    @classmethod
    def normalize_enum_value(cls, value: Any) -> Any:
        """Normaliza el valor de un enum a mayúsculas y elimina espacios, o lo deja como None si es vacío."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_optional_date(cls, value: Any) -> Any:
        """Valida que los campos de fecha opcionales sean fechas válidas o None, y no cadenas vacías."""
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("date_mode")
    @classmethod
    def validate_date_mode(cls, value: str) -> str:
        """Valida que el modo de fecha sea 'overlap', 'start_date' o 'end_date'."""
        normalized = value.strip().lower()
        if normalized not in VALID_DATE_MODES:
            raise ValueError("date_mode invalido")
        return normalized
