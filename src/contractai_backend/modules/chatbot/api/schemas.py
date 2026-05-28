"""Schemas for the chatbot API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to the chatbot.")
    thread_id: int | None = Field(default=None, description="ID de la conversación.")


class ChatResponse(BaseModel):
    response: str = Field(..., description="The chatbot's response to the user's message.")
    thread_id: int = Field(..., description="ID de la conversación.")


class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, pattern=r".*\S.*", description="Conversation title.")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Reject blank conversation titles."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, pattern=r".*\S.*", description="Conversation title.")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Reject blank conversation titles."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty.")
        return cleaned


class ConversationRead(BaseModel):
    id: int
    title: str
    organization_id: int
    user_id: int
    content: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationList(BaseModel):
    id: int
    title: str
    organization_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
