"""Schemas for template authoring endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...documents.domain import DocumentType
from ..domain.entities import TemplateContent, TemplateFormatTable, TemplateTable
from ..domain.formats import normalize_format_code
from ..domain.value_objs import TemplateState


class GenerateTemplateDraftRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    jurisdiction: str | None = None
    document_type: DocumentType | None = None
    format_code: str

    @field_validator("format_code")
    @classmethod
    def validate_format_code(cls, value: str) -> str:
        """Normaliza el codigo tecnico del formato."""
        return normalize_format_code(value)


class TemplateUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class TemplateDraftResponse(BaseModel):
    name: str
    description: str | None = None
    content: TemplateContent
    warnings: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    usage: TemplateUsage | None = None


class TemplateResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None = None
    document_type: DocumentType
    template_format_id: int | None = None
    format_code: str | None = None
    format_label: str | None = None
    content: TemplateContent
    created_at: datetime | None = None
    state: TemplateState

    model_config = ConfigDict(from_attributes=True)


def build_template_response(
    template: TemplateTable,
    template_format: TemplateFormatTable | None = None,
) -> TemplateResponse:
    """Serializa una entidad de plantilla."""
    return TemplateResponse(
        id=template.id,
        organization_id=template.organization_id,
        name=template.name,
        description=template.description,
        document_type=template.document_type,
        template_format_id=template.template_format_id,
        format_code=template_format.format_code if template_format is not None else None,
        format_label=template_format.label if template_format is not None else None,
        content=TemplateContent.model_validate(template.content),
        created_at=template.created_at,
        state=template.state,
    )


class PersistedTemplateDraftResponse(BaseModel):
    template: TemplateResponse
    warnings: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    usage: TemplateUsage | None = None


class PreviewTemplateRequest(BaseModel):
    document_type: DocumentType | None = None
    format_code: str
    content: TemplateContent
    sample_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("format_code")
    @classmethod
    def validate_preview_format_code(cls, value: str) -> str:
        """Normaliza el codigo tecnico del formato en preview."""
        return normalize_format_code(value)


class PreviewTemplateResponse(BaseModel):
    markdown: str
    resolved_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CreateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    document_type: DocumentType | None = None
    format_code: str
    content: TemplateContent

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """Normaliza el nombre obligatorio."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Normaliza la descripcion opcional."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("format_code")
    @classmethod
    def validate_create_format_code(cls, value: str) -> str:
        """Normaliza el codigo tecnico del formato."""
        return normalize_format_code(value)


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: TemplateContent | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        """Normaliza el nombre opcional."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_optional_description(cls, value: str | None) -> str | None:
        """Normaliza la descripcion opcional."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "UpdateTemplateRequest":
        """Verifica que el patch incluya al menos un cambio."""
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self


class TemplateFormatResponse(BaseModel):
    id: int
    document_type: DocumentType
    format_code: str
    label: str
    default_name: str
    default_description: str | None = None
