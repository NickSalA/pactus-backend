"""Defines the database tables for templates and template formats."""

import re
import unicodedata
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

    @model_validator(mode="after")
    def populate_placeholder(self) -> "TemplateField":
        if self.placeholder is None:
            self.placeholder = self.build_placeholder(key=self.key, label=self.label, field_type=self.type)
        return self

    @staticmethod
    def build_placeholder(*, key: str, label: str, field_type: str) -> str:
        tokens = TemplateField._field_tokens(key=key, label=label)
        if field_type == "date":
            return "Ej. 2026-12-31"
        if field_type == "time":
            return "Ej. 09:00"
        if "partida" in tokens:
            return "Ej. 11012345"
        if "registro" in tokens:
            return "Ej. Registro de Personas Juridicas de Lima"
        if field_type == "number":
            if "porcentaje" in tokens:
                return "Ej. 10"
            if tokens & {"monto", "valor", "precio", "renta", "retribucion", "utilidad"}:
                return "Ej. 1500"
            return "Ej. 1000"
        if field_type == "boolean":
            return "Ej. Sí"
        if "ruc" in tokens:
            return "Ej. 20123456789"
        if "dni" in tokens:
            return "Ej. 12345678"
        if "email" in tokens or "correo" in tokens:
            return "Ej. contacto@empresa.com"
        if "telefono" in tokens or "celular" in tokens:
            return "Ej. +51 999 888 777"
        if "domicilio" in tokens or "direccion" in tokens:
            return "Ej. Av. Javier Prado 123, Lima"
        if {"razon", "social"} <= tokens:
            return "Ej. Inversiones Andinas S.A.C."
        if "nombre" in tokens:
            return "Ej. Juan Perez"
        if "moneda" in tokens:
            return "Ej. USD"
        if "jurisdiccion" in tokens or ({"camara", "comercio"} <= tokens):
            return "Ej. Lima"
        if "plazo" in tokens or "duracion" in tokens:
            return "Ej. 12 meses"
        if "objeto" in tokens:
            return "Ej. Administracion integral del hotel"
        return f"Ej. {label}"

    @staticmethod
    def _field_tokens(*, key: str, label: str) -> set[str]:
        normalized = unicodedata.normalize("NFD", key + " " + label)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
        return {token for token in normalized.split("_") if token}


class TemplateContractDateMapping(BaseModel):
    start_date_field: str = Field(default=..., description="Field key used as the contract start date")
    end_date_field: str = Field(default=..., description="Field key used as the contract end date")

    @field_validator("start_date_field", "end_date_field")
    @classmethod
    def validate_field_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Contract date mapping fields cannot be empty")
        return cleaned

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
