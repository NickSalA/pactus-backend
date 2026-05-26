"""DTOs for structured contract queries by document type."""

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator

from ...domain import CurrencyType, DocumentState

VALID_OPERATIONS_COMMON = {"count", "list"}
VALID_OPERATIONS_COMPANY = {"count", "list", "ranking", "services_ranking", "client_services_ranking"}
VALID_OPERATIONS_LABOR = {"count", "list"}
VALID_DATE_MODES = {"overlap", "start_date", "end_date"}
VALID_SORT_DIRECTIONS = {"asc", "desc"}


class CompanyContractQueryDTO(BaseModel):
    operation: str
    client: str | None = None
    ruc: str | None = None
    contract_name: str | None = None
    service_name: str | None = None
    service_id: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    currency: CurrencyType | None = None
    state: DocumentState | None = None
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
        normalized = value.strip().lower()
        if normalized not in VALID_OPERATIONS_COMPANY:
            raise ValueError(f"La operacion debe ser una de: {', '.join(sorted(VALID_OPERATIONS_COMPANY))}.")
        return normalized

    @field_validator("client", "contract_name", "service_name", "ruc")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("service_id")
    @classmethod
    def validate_service_id(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value <= 0:
            raise ValueError("service_id invalido")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("state", mode="before")
    @classmethod
    def normalize_enum_value(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_optional_date(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("date_mode")
    @classmethod
    def validate_date_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_DATE_MODES:
            raise ValueError("date_mode invalido")
        return normalized

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in {"client", "name", "value", "start_date", "end_date", "currency", "total_value", "contracts_count"}:
            raise ValueError("sort_by invalido para contratos COMPANY")
        return normalized

    @field_validator("sort_direction")
    @classmethod
    def validate_sort_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_SORT_DIRECTIONS:
            raise ValueError("sort_direction invalido")
        return normalized


class LaborContractQueryDTO(BaseModel):
    operation: str
    worker_name: str | None = None
    worker_document_number: str | None = None
    position: str | None = None
    contract_name: str | None = None
    contract_modality: str | None = None
    salary_periodicity: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    currency: CurrencyType | None = None
    state: DocumentState | None = None
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
        normalized = value.strip().lower()
        if normalized not in VALID_OPERATIONS_LABOR:
            raise ValueError(f"La operacion debe ser una de: {', '.join(sorted(VALID_OPERATIONS_LABOR))}. Ranking no disponible para contratos LABOR.")
        return normalized

    @field_validator("worker_name", "worker_document_number", "position", "contract_name", "contract_modality", "salary_periodicity")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("state", mode="before")
    @classmethod
    def normalize_enum_value(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def normalize_optional_date(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("date_mode")
    @classmethod
    def validate_date_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_DATE_MODES:
            raise ValueError("date_mode invalido")
        return normalized

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in {"worker_name", "position", "salary_value", "start_date", "end_date", "currency"}:
            raise ValueError("sort_by invalido para contratos LABOR")
        return normalized

    @field_validator("sort_direction")
    @classmethod
    def validate_sort_direction(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_SORT_DIRECTIONS:
            raise ValueError("sort_direction invalido")
        return normalized