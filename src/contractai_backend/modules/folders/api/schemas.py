"""Schemas for folders module API requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from ....modules.users.domain.value_objs import UserRole


class FolderCreateRequest(BaseModel):
    """Request schema for creating document folders."""

    name: str = Field(..., description="Folder display name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class FolderUpdateRequest(BaseModel):
    """Request schema for updating document folders."""

    name: str | None = None

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
    def validate_non_empty_patch(self) -> "FolderUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self


class FolderResponse(BaseModel):
    """Response schema for folder records."""

    id: int = Field(..., description="Unique identifier of the folder")
    organization_id: int = Field(..., description="Owning organization")
    name: str = Field(..., description="Folder display name")
    owner_role: UserRole = Field(..., description="Role group that owns the folder")
    created_by: int = Field(..., description="Identifier of the user who created the folder")
    created_by_name: str | None = Field(default=None, description="Display name of the folder creator")
    created_by_email: str | None = Field(default=None, description="Email of the folder creator")
    documents_count: int = Field(default=0, description="How many documents are assigned to the folder")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
