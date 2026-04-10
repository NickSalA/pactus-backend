"""Schemas for document-related API requests and responses."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from ....modules.documents.domain import CurrencyType, DocumentState, DocumentType
from ....modules.users.domain.value_objs import UserRole


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


class DocumentBase(BaseModel):
    """Base schema for document-related requests and responses."""

    name: str = Field(..., description="Name of the document")
    client: str = Field(..., description="Client associated with the document")
    type: DocumentType = Field(..., description="Type of the document")
    start_date: date = Field(..., description="Start date of the document period")
    end_date: date = Field(..., description="End date of the document period")
    form_data: dict[str, Any] = Field(..., description="Structured JSON payload stored in the form_data column")

    @field_validator("name", "client")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class DocumentDraftBase(BaseModel):
    """Nullable contract metadata accepted during upload/import autofill flows."""

    name: str | None = Field(default=None, description="Name of the document")
    client: str | None = Field(default=None, description="Client associated with the document")
    type: DocumentType | None = Field(default=None, description="Type of the document")
    start_date: date | None = Field(default=None, description="Start date of the document period")
    end_date: date | None = Field(default=None, description="End date of the document period")
    form_data: dict[str, Any] = Field(default_factory=dict, description="Structured JSON payload stored in the form_data column")

    @field_validator("name", "client")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned

    @field_validator("end_date")
    @classmethod
    def validate_optional_end_date(cls, end_date: date | None, info: ValidationInfo) -> date | None:
        if end_date is None:
            return None
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date.")
        return end_date

    @field_validator("form_data")
    @classmethod
    def clean_form_data(cls, form_data: dict[str, Any]) -> dict[str, Any]:
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
        description="Services associated to the document through documents_services",
    )

    @field_validator("service_items")
    @classmethod
    def validate_unique_service_ids(cls, service_items: list[DocumentServiceItemRequest]) -> list[DocumentServiceItemRequest]:
        service_ids = [item.service_id for item in service_items]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service_items contains duplicated service_id values.")
        return service_items


class CreateDocumentRequest(CreateDocumentDraftRequest):
    """Request schema for creating a new document."""

    name: str = Field(..., description="Name of the document")
    client: str = Field(..., description="Client associated with the document")
    type: DocumentType = Field(..., description="Type of the document")
    start_date: date = Field(..., description="Start date of the document period")
    end_date: date = Field(..., description="End date of the document period")
    form_data: dict[str, Any] = Field(..., description="Structured JSON payload stored in the form_data column")


class UpdateDocumentRequest(BaseModel):
    """Request schema for updating an existing document."""

    name: str | None = None
    client: str | None = None
    type: DocumentType | None = None
    start_date: date | None = None
    end_date: date | None = None
    form_data: dict[str, Any] | None = None
    state: DocumentState | None = None
    folder_id: int | None = Field(default=None, gt=0)
    service_items: list[DocumentServiceItemRequest] | None = None

    @field_validator("name", "client")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned

    @field_validator("service_items")
    @classmethod
    def validate_optional_unique_service_ids(cls, service_items: list[DocumentServiceItemRequest] | None) -> list[DocumentServiceItemRequest] | None:
        if service_items is None:
            return None
        service_ids = [item.service_id for item in service_items]
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("service_items contains duplicated service_id values.")
        return service_items

    @field_validator("form_data")
    @classmethod
    def clean_optional_form_data(cls, form_data: dict[str, Any] | None) -> dict[str, Any] | None:
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
    name: str | None = Field(default=None, description="Name of the document")
    client: str | None = Field(default=None, description="Client associated with the document")
    type: DocumentType | None = Field(default=None, description="Type of the document")
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
