"""Routes related to chatbot token usage."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .....shared.api.dependencies.security import CurrentUserDep
from ...api.dependencies import get_token_usage_service
from ...api.schemas import TokenUsageRead, TokenUsageSummary
from ...application import TokenUsageService

router = APIRouter()
TokenUsageServiceDep = Annotated[TokenUsageService, Depends(get_token_usage_service)]


@router.get(path="/conversation/{conversation_id}", response_model=list[TokenUsageRead])
async def get_conversation_token_usage(
    conversation_id: int,
    service: TokenUsageServiceDep,
):
    """Endpoint para obtener el historial de uso de tokens de una conversación."""
    usage_records = await service.get_conversation_usage(conversation_id=conversation_id)
    return [TokenUsageRead.model_validate(record) for record in usage_records]


@router.get(path="/summary", response_model=TokenUsageSummary)
async def get_token_usage_summary(
    service: TokenUsageServiceDep,
    current_user: CurrentUserDep,
    conversation_id: int | None = Query(default=None, description="Filter by conversation ID"),
):
    """Endpoint para obtener un resumen del uso de tokens."""
    summary_dto = await service.get_summary(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        conversation_id=conversation_id,
    )

    return TokenUsageSummary(
        total_input_tokens=summary_dto.total_input_tokens,
        total_output_tokens=summary_dto.total_output_tokens,
        total_tokens=summary_dto.total_tokens,
        total_input_cost_usd=summary_dto.total_input_cost_usd,
        total_output_cost_usd=summary_dto.total_output_cost_usd,
        total_cost_usd=summary_dto.total_cost_usd,
        usage_count=summary_dto.usage_count,
    )
