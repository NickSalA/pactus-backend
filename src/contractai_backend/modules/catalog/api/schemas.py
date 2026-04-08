"""Schemas for catalog module API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ServiceResponse(BaseModel):
    """Schema for service catalog items available to the frontend."""

    id: int = Field(..., description="Unique identifier of the service")
    name: str = Field(..., description="Display name of the service")
    is_active: bool = Field(..., description="Whether the service is currently enabled")
    documents_count: int = Field(default=0, description="How many contracts reference the service")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ServiceCreateRequest(BaseModel):
    """Request schema for creating catalog services."""

    name: str = Field(..., description="Display name of the service")
    is_active: bool = Field(default=True, description="Whether the service starts active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class ServiceUpdateRequest(BaseModel):
    """Request schema for updating catalog services."""

    name: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "ServiceUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self
