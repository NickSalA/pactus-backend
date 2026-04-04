"""Schemas for template authoring endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from ..domain.entities import TemplateContent


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
