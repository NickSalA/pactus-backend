"""Schemas for template authoring endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.entities import TemplateContent
from ..domain.value_objs import TemplateState


class GenerateTemplateDraftRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    contract_type: str | None = None
    jurisdiction: str | None = None
    preferred_fields: list[str] = Field(default_factory=list)


class TemplateDraftResponse(BaseModel):
    name: str
    description: str | None = None
    content: TemplateContent
    warnings: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)


class TemplateResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None = None
    content: TemplateContent
    created_at: datetime | None = None
    state: TemplateState

    model_config = ConfigDict(from_attributes=True)


class PersistedTemplateDraftResponse(BaseModel):
    template: TemplateResponse
    warnings: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)


class PreviewTemplateRequest(BaseModel):
    content: TemplateContent
    sample_data: dict[str, Any] = Field(default_factory=dict)


class PreviewTemplateResponse(BaseModel):
    markdown: str
    resolved_payload: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    content: TemplateContent

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: TemplateContent | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned
