"""Defines the database tables for templates and template formats."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ...documents.domain import DocumentType
from .formats import normalize_format_code
from .value_objs import TemplateState


class TemplateField(BaseModel):
    key: str = Field(default=..., description="Unique identifier for the field")
    label: str = Field(default=..., description="Human-readable label for the field")
    type: str = Field(default="text", description="Data type of the field (e.g., string, number, date)")
    required: bool = Field(default=False, description="Indicates if the field is required")
    placeholder: str | None = Field(default=None, description="Optional example shown in the UI input")

    @field_validator("placeholder")
    @classmethod
    def normalize_placeholder(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TemplateContractDateMapping(BaseModel):
    start_date_field: str = Field(default=..., description="Field key used as the contract start date")
    end_date_field: str = Field(default=..., description="Field key used as the contract end date")

    @field_validator("start_date_field", "end_date_field")
    @classmethod
    def validate_field_key(cls, value: str) -> str:
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Contract date mapping fields cannot be empty")

    @model_validator(mode="after")
    def validate_distinct_fields(self) -> "TemplateContractDateMapping":
        if self.start_date_field == self.end_date_field:
            raise ValueError("Contract date mapping fields must be different")
        return self


class TemplateContent(BaseModel):
    body_md: str = Field(default=..., description="The main content of the template")
    fields: list[TemplateField] = Field(default=..., description="List of fields in the template")
    operational_fields: list[TemplateField] = Field(
        default_factory=list,
        description="Extra form fields required by backend logic but not necessarily rendered in body_md",
    )
    version: str | None = Field(default="1.0", description="Version of the template")
    contract_date_mapping: TemplateContractDateMapping | None = Field(
        default=None,
        description="Maps which template fields represent the contract start and end dates",
    )


class TemplateTable(BaseTable, table=True):
    __tablename__ = "document_templates"

    organization_id: int = Field(sa_column=Column("organization_id", Integer, nullable=False, index=True))
    name: str = Field(sa_column=Column("name", String(length=255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column("description", Text, nullable=True))
    document_type: DocumentType = Field(
        sa_column=Column("document_type", ENUM(DocumentType, name="document_type", create_type=False), nullable=False)
    )
    content: dict[str, Any] = Field(sa_column=Column("content", JSONB, nullable=False))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(tz=UTC), sa_column=Column("created_at", DateTime(timezone=True), nullable=False)
    )
    state: TemplateState = Field(
        default=TemplateState.DRAFT, sa_column=Column("state", ENUM(TemplateState, name="document_template_state"), nullable=False)
    )
    template_format_id: int | None = Field(default=None, sa_column=Column("template_format_id", Integer, nullable=True))

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: Any) -> dict[str, Any]:
        """Valida que el diccionario 'v' cumpla con el esquema TemplateContent."""
        if isinstance(v, dict):
            TemplateContent(**v)
            return v
        if isinstance(v, TemplateContent):
            return v.model_dump()
        raise ValueError("Content must be a dictionary or TemplateContent instance")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Valida que el nombre de la plantilla no esté vacío o solo contenga espacios."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("organization_id")
    @classmethod
    def validate_organization_id(cls, v):
        """Valida que el ID de la organización sea un número entero positivo."""
        if v <= 0:
            raise ValueError("Organization ID must be a positive integer")
        return v


class TemplateFormatTable(BaseTable, table=True):
    __tablename__ = "template_formats"

    document_type: DocumentType = Field(
        sa_column=Column("document_type", ENUM(DocumentType, name="document_type", create_type=False), nullable=False)
    )
    format_code: str = Field(default=..., sa_column=Column("format_code", String(length=255), nullable=False))
    label: str = Field(default=..., sa_column=Column("label", String(length=255), nullable=False))
    default_description: str | None = Field(default=None, sa_column=Column("default_description", Text, nullable=True))
    default_name: str | None = Field(default=None, sa_column=Column("default_name", String(length=255), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column("is_active", nullable=False))

    @field_validator("format_code")
    @classmethod
    def validate_format_code(cls, value: str) -> str:
        """Valida y normaliza el codigo tecnico del formato."""
        return normalize_format_code(value)
