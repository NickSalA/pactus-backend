"""Application DTOs for document requests and responses."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ...domain import CurrencyType, DocumentState, DocumentType


class DocumentServiceItemBase(BaseModel):
    """Base schema for a service associated to a document."""

    service_id: int = Field(..., gt=0, description="Unique identifier of the related service")
    description: str | None = Field(default=None, description="Optional free-text detail for this service within the document")
    value: float = Field(..., ge=0, description="Amount assigned to the related service")
    currency: CurrencyType = Field(..., description="Currency used for the related service amount")
    start_date: date = Field(..., description="Start date for the service period inside the contract")
    end_date: date = Field(..., description="End date for the service period inside the contract")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, end_date: date, info: ValidationInfo) -> date:
        """Ensures end date is not earlier than start date."""
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return end_date


class DocumentServiceItemRequest(DocumentServiceItemBase):
    """Request schema for document-service associations."""


class DocumentServiceItemResponse(DocumentServiceItemBase):
    """Response schema for document-service associations."""

    id: int = Field(..., description="Unique identifier of the document-service association")

    model_config = ConfigDict(from_attributes=True)


class CompanyContractBase(BaseModel):
    """Company-specific contract data."""

    ruc: str | None = Field(default=None, description="RUC of the company counterparty")
    client: str | None = Field(default=None, description="Company counterparty name")

    @field_validator("ruc", "client")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        """Rejects blank text when optional company fields are provided."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")


class CompanyContractRequest(CompanyContractBase):
    """Request schema for company-specific contract data."""


class CompanyContractResponse(CompanyContractBase):
    """Response schema for company-specific contract data."""

    id: int = Field(..., description="Unique identifier of the company contract row")
    document_id: int = Field(..., description="Related document identifier")
    created_at: datetime = Field(..., description="Company contract creation timestamp")
    updated_at: datetime = Field(..., description="Last company contract update timestamp")

    model_config = ConfigDict(from_attributes=True)


class LaborContractBase(BaseModel):
    """Labor-specific contract data."""

    worker_name: str | None = None
    worker_document_number: str | None = None
    position: str | None = None
    salary_value: float | None = Field(default=None, ge=0)
    salary_currency: CurrencyType | None = None
    salary_periodicity: str | None = None
    contract_modality: str | None = None

    @field_validator("worker_name", "worker_document_number", "position", "salary_periodicity", "contract_modality")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        """Rejects blank text when optional labor fields are provided."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")


class LaborContractRequest(LaborContractBase):
    """Request schema for labor-specific contract data."""


class LaborContractResponse(LaborContractBase):
    """Response schema for labor-specific contract data."""

    id: int = Field(..., description="Unique identifier of the labor contract row")
    document_id: int = Field(..., description="Related document identifier")
    created_at: datetime = Field(..., description="Labor contract creation timestamp")
    updated_at: datetime = Field(..., description="Last labor contract update timestamp")

    model_config = ConfigDict(from_attributes=True)


class DocumentBase(BaseModel):
    """Base schema for document-related requests and responses."""

    type: str = Field(..., description="Document source/template type")
    start_date: date = Field(..., description="Start date of the document period")
    end_date: date = Field(..., description="End date of the document period")
    form_data: dict[str, Any] = Field(..., description="Structured JSON payload stored in the form_data column")

    @field_validator("type")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        """Rejects blank document source types."""
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")


class DocumentDraftBase(BaseModel):
    """Nullable contract metadata accepted during upload/import autofill flows."""

    type: str | None = Field(default=None, description="Document source/template type")
    contract_type: DocumentType | None = Field(default=None, description="Functional contract class used for routing and permissions")
    name: str | None = Field(default=None, description="Legacy document name accepted during transition")
    client: str | None = Field(default=None, description="Legacy counterparty accepted during transition")
    start_date: date | None = Field(default=None, description="Start date of the document period")
    end_date: date | None = Field(default=None, description="End date of the document period")
    form_data: dict[str, Any] = Field(default_factory=dict, description="Structured JSON payload stored in the form_data column")

    company_contract: CompanyContractRequest | None = None
    labor_contract: LaborContractRequest | None = None

    @field_validator("type", "name", "client")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        """Rejects blank text when optional document metadata is provided."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")

    @field_validator("end_date")
    @classmethod
    def validate_optional_end_date(cls, end_date: date | None, info: ValidationInfo) -> date | None:
        """Ensures optional end date is not earlier than start date."""
        if end_date is None:
            return None
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return end_date

    @field_validator("form_data")
    @classmethod
    def clean_form_data(cls, form_data: dict[str, Any]) -> dict[str, Any]:
        """Removes legacy nested service keys from form data."""
        cleaned_form_data = dict(form_data)
        cleaned_form_data.pop("licenses", None)
        cleaned_form_data.pop("services", None)
        cleaned_form_data.pop("support", None)
        return cleaned_form_data


class CreateDocumentDraftRequest(DocumentDraftBase):
    """Request schema for creating a document with backend autofill."""

    state: DocumentState | None = Field(default=None, description="Optional manual document state")
    folder_id: int | None = Field(default=None, gt=0, description="Optional folder assigned to the document")
    service_items: list[DocumentServiceItemRequest] = Field(
        default_factory=list,
        description="Services associated to the company contract",
    )

    @field_validator("service_items")
    @classmethod
    def validate_unique_service_ids(cls, service_items: list[DocumentServiceItemRequest]) -> list[DocumentServiceItemRequest]:
        """Rejects duplicate service IDs within one document payload."""
        service_ids = [item.service_id for item in service_items]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service_items contains duplicated service_id values.")
        return service_items


class CreateDocumentRequest(CreateDocumentDraftRequest):
    """Request schema for creating a new document."""

    type: str = Field(..., description="Document source/template type")
    start_date: date = Field(..., description="Start date of the document period")
    end_date: date = Field(..., description="End date of the document period")
    form_data: dict[str, Any] = Field(..., description="Structured JSON payload stored in the form_data column")


class UpdateDocumentRequest(BaseModel):
    """Request schema for updating an existing document."""

    type: str | None = None
    contract_type: DocumentType | None = None
    name: str | None = None
    client: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    form_data: dict[str, Any] | None = None
    state: DocumentState | None = None
    folder_id: int | None = Field(default=None, gt=0)
    service_items: list[DocumentServiceItemRequest] | None = None
    company_contract: CompanyContractRequest | None = None
    labor_contract: LaborContractRequest | None = None

    @field_validator("type", "name", "client")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        """Rejects blank text when optional document metadata is provided."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")

    @field_validator("service_items")
    @classmethod
    def validate_optional_unique_service_ids(cls, service_items: list[DocumentServiceItemRequest] | None) -> list[DocumentServiceItemRequest] | None:
        """Rejects duplicate service IDs when service items are patched."""
        if service_items is None:
            return None
        service_ids = [item.service_id for item in service_items]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service_items contains duplicated service_id values.")
        return service_items

    @field_validator("form_data")
    @classmethod
    def clean_optional_form_data(cls, form_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Removes legacy nested service keys from optional form data."""
        if form_data is None:
            return None
        cleaned_form_data = dict(form_data)
        cleaned_form_data.pop("licenses", None)
        cleaned_form_data.pop("services", None)
        cleaned_form_data.pop("support", None)
        return cleaned_form_data


class DocumentResponse(BaseModel):
    """Response schema for document data."""

    id: int = Field(..., description="Unique identifier of the document")
    type: str | None = Field(default=None, description="Document source/template type")
    start_date: date | None = Field(default=None, description="Start date of the document period")
    end_date: date | None = Field(default=None, description="End date of the document period")
    form_data: dict[str, Any] = Field(default_factory=dict, description="Structured JSON payload stored in the form_data column")
    state: DocumentState | None = Field(default=None, description="Current state of the document")
    folder_id: int | None = Field(default=None, description="Folder assigned to the document")
    file_path: str | None = Field(default=None, description="Storage path of the associated file")
    file_name: str | None = Field(default=None, description="Original name of the associated file")
    service_items: list[DocumentServiceItemResponse] = Field(
        default_factory=list,
        description="Services associated to this document",
    )
    company_contract: CompanyContractResponse | None = None
    labor_contract: LaborContractResponse | None = None
    created_at: datetime = Field(..., description="Document creation timestamp")
    updated_at: datetime = Field(..., description="Last document update timestamp")

    model_config = ConfigDict(from_attributes=True)


class DocumentCatalogServiceResponse(BaseModel):
    """Backward-compatible lightweight service catalog response."""

    id: int = Field(..., description="Unique identifier of the service")
    name: str = Field(..., description="Display name of the service")

    model_config = ConfigDict(from_attributes=True)


class DocumentFileUrlResponse(BaseModel):
    """Response schema with a temporary URL to access a document file."""

    url: str = Field(..., description="Signed URL for temporary access")


class FileRequest(BaseModel):
    """Request schema for file uploads."""

    content: bytes = Field(..., description="Binary content of the file", repr=False)
    filename: str = Field(..., description="Original name of the file")
    content_type: str = Field(..., description="MIME type of the file")
