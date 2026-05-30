"""Schemas for the chatbot API endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message to the chatbot.")
    thread_id: int | None = Field(default=None, description="ID de la conversación.")


class ChatResponse(BaseModel):
    response: str = Field(..., description="The chatbot's response to the user's message.")
    thread_id: int = Field(..., description="ID de la conversación.")


class ConversationCreate(BaseModel):
    title: str
    organization_id: int
    user_id: int


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

    model_config = ConfigDict(from_attributes=True)


class TokenUsageRead(BaseModel):
    id: int
    conversation_id: int
    message_index: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: Decimal
    output_cost_usd: Decimal
    total_cost_usd: Decimal
    model_used: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenUsageSummary(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_input_cost_usd: Decimal
    total_output_cost_usd: Decimal
    total_cost_usd: Decimal
    usage_count: int
