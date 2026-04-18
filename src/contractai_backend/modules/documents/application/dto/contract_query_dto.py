"""DTOs for structured contract queries."""

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator

from ...domain import CurrencyType, DocumentState, DocumentType

VALID_OPERATIONS = {"count", "list", "ranking"}
VALID_DATE_MODES = {"overlap", "start_date", "end_date"}
VALID_SORT_FIELDS = {"client", "name", "value", "start_date", "end_date", "currency", "total_value", "contracts_count"}
VALID_SORT_DIRECTIONS = {"asc", "desc"}


class ContractQueryDTO(BaseModel):
    operation: str
    client: str | None = None
    contract_name: str | None = None
    service_name: str | None = None
    service_id: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    currency: CurrencyType | None = None
    state: DocumentState | None = None
    document_type: DocumentType | None = None
    period_start: date | None = None
    period_end: date | None = None
    date_mode: str = "overlap"
    currently_active: bool | None = None
    sort_by: str | None = None
    sort_direction: str = "asc"
    limit: int | None = None

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        """Valida que la operacion sea 'count', 'list' o 'ranking'."""
        normalized = value.strip().lower()
        if normalized not in VALID_OPERATIONS:
            raise ValueError("La operacion debe ser 'count', 'list' o 'ranking'.")
        return normalized

    @field_validator("client", "contract_name", "service_name")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        """Valida que los campos de texto opcionales no sean solo espacios en blanco."""
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @field_validator("service_id")
    @classmethod
    def validate_service_id(cls, value: int | None) -> int | None:
        """Valida que el servicio sea un identificador positivo cuando está presente."""
        if value is None:
            return None
        if value <= 0:
            raise ValueError("service_id invalido")
        return value

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

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str | None) -> str | None:
        """Valida el campo de ordenamiento cuando esta presente."""
        if value is None:
            return None

        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in VALID_SORT_FIELDS:
            raise ValueError("sort_by invalido")
        return normalized

    @field_validator("sort_direction")
    @classmethod
    def validate_sort_direction(cls, value: str) -> str:
        """Valida la direccion de ordenamiento."""
        normalized = value.strip().lower()
        if normalized not in VALID_SORT_DIRECTIONS:
            raise ValueError("sort_direction invalido")
        return normalized
