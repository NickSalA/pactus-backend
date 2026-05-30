"""DTOs for best-effort document autofill extraction."""

from datetime import date

from pydantic import BaseModel, Field

from ...domain import CurrencyType, DocumentType


class ExtractedDocumentFormData(BaseModel):
    """Structured values inferred from the document body."""

    value: float | None = None
    currency: CurrencyType | None = None


class ExtractedDocumentServiceItem(BaseModel):
    """Best-effort service item candidate inferred from a contract."""

    service_id: int | None = None
    description: str | None = None
    value: float | None = None
    currency: CurrencyType | None = None
    start_date: date | None = None
    end_date: date | None = None


class ExtractedDocumentData(BaseModel):
    """Best-effort metadata extracted from a contract file."""

    name: str | None = None
    client: str | None = None
    ruc: str | None = None
    worker_name: str | None = None
    worker_document_number: str | None = None
    position: str | None = None
    type: DocumentType | None = None
    start_date: date | None = None
    end_date: date | None = None
    labor_monthly_value: float | None = None
    labor_monthly_currency: CurrencyType | None = None
    salary_periodicity: str | None = None
    contract_modality: str | None = None
    form_data: ExtractedDocumentFormData = Field(default_factory=ExtractedDocumentFormData)
    service_items: list[ExtractedDocumentServiceItem] = Field(default_factory=list)
