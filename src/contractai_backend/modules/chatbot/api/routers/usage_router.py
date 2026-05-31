"""Routes related to chatbot token usage."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import select

from .....shared.api.dependencies.security import CurrentUserDep
from ...api.dependencies import get_token_usage_repository
from ...api.schemas import TokenUsageRead, TokenUsageSummary
from ...domain.entities import ConversationTable
from ...infrastructure.token_usage_repo import TokenUsageRepository

router = APIRouter()
TokenUsageRepoDep = Annotated[TokenUsageRepository, Depends(get_token_usage_repository)]


@router.get(path="/conversation/{conversation_id}", response_model=list[TokenUsageRead])
async def get_conversation_token_usage(
    conversation_id: int,
    repo: TokenUsageRepoDep,
):
    """Endpoint para obtener el historial de uso de tokens de una conversación."""
    usage_records = await repo.get_by_conversation_id(conversation_id=conversation_id)
    return [TokenUsageRead.model_validate(record) for record in usage_records]


@router.get(path="/summary", response_model=TokenUsageSummary)
async def get_token_usage_summary(
    repo: TokenUsageRepoDep,
    current_user: CurrentUserDep,
    conversation_id: int | None = Query(default=None, description="Filter by conversation ID"),
):
    """Endpoint para obtener un resumen del uso de tokens."""
    async with repo.session:
        if conversation_id is not None:
            usage_records = await repo.get_by_conversation_id(conversation_id=conversation_id)
        else:
            conv_query = select(ConversationTable).where(
                ConversationTable.user_id == current_user.id,
                ConversationTable.organization_id == current_user.organization_id,
            )
            conv_result = await repo.session.exec(statement=conv_query)
            conversations = conv_result.all()
            conv_ids = [c.id for c in conversations]

            usage_records = []
            for cid in conv_ids:
                usage = await repo.get_by_conversation_id(cid)
                usage_records.extend(usage)

    if not usage_records:
        return TokenUsageSummary(
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            total_input_cost_usd=Decimal("0"),
            total_output_cost_usd=Decimal("0"),
            total_cost_usd=Decimal("0"),
            usage_count=0,
        )

    total_input_tokens = sum(r.input_tokens for r in usage_records)
    total_output_tokens = sum(r.output_tokens for r in usage_records)
    total_tokens = sum(r.total_tokens for r in usage_records)
    total_input_cost = Decimal(str(sum(r.input_cost_usd for r in usage_records)))
    total_output_cost = Decimal(str(sum(r.output_cost_usd for r in usage_records)))
    total_cost = Decimal(str(sum(r.total_cost_usd for r in usage_records)))

    return TokenUsageSummary(
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_tokens,
        total_input_cost_usd=total_input_cost,
        total_output_cost_usd=total_output_cost,
        total_cost_usd=total_cost,
        usage_count=len(usage_records),
    )
