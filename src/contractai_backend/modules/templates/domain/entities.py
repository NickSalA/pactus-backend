"""Defines the database table for templates, including fields for organization ID, name, description, content, and creation timestamp."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlmodel import Field

from ....core.domain.base import BaseTable
from .value_objs import TemplateState


class TemplateField(BaseModel):
    key: str = Field(default=..., description="Unique identifier for the field")
    label: str = Field(default=..., description="Human-readable label for the field")
    type: str = Field(default="text", description="Data type of the field (e.g., string, number, date)")
    required: bool = Field(default=False, description="Indicates if the field is required")


class TemplateContent(BaseModel):
    body_md: str = Field(default=..., description="The main content of the template")
    fields: list[TemplateField] = Field(default=..., description="List of fields in the template")
    version: str | None = Field(default="1.0", description="Version of the template")


class TemplateTable(BaseTable, table=True):
    __tablename__ = "document_templates"

    organization_id: int = Field(sa_column=Column("organization_id", Integer, nullable=False, index=True))
    name: str = Field(sa_column=Column("name", String(length=255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column("description", Text, nullable=True))
    content: dict[str, Any] = Field(sa_column=Column("content", JSONB, nullable=False))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(tz=UTC), sa_column=Column("created_at", DateTime(timezone=True), nullable=False)
    )
    state: TemplateState = Field(
        default=TemplateState.DRAFT, sa_column=Column("state", ENUM(TemplateState, name="document_template_state"), nullable=False)
    )

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
