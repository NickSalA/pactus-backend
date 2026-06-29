"""Application DTOs for the service catalog module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ServiceResponse(BaseModel):
    """Service catalog item returned by application use cases."""

    id: int = Field(..., description="Unique identifier of the service")
    name: str = Field(..., description="Display name of the service")
    is_active: bool = Field(..., description="Whether the service is currently enabled")
    documents_count: int = Field(default=0, description="How many contracts reference the service")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ServiceCreateRequest(BaseModel):
    """Data required to create a catalog service."""

    name: str = Field(..., description="Display name of the service")
    is_active: bool = Field(default=True, description="Whether the service starts active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Rejects blank service names."""
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")


class ServiceUpdateRequest(BaseModel):
    """Data accepted when updating a catalog service."""

    name: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        """Rejects blank service names when provided."""
        if value is None:
            return None
        if cleaned := value.strip():
            return cleaned
        else:
            raise ValueError("Field cannot be empty.")

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "ServiceUpdateRequest":
        """Requires at least one field in patch requests."""
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self
