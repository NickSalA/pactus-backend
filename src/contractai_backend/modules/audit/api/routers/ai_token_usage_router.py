"""Router for AI token usage audit queries."""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.audit.api.dependencies import get_ai_token_tracking_service
from contractai_backend.modules.audit.api.schemas import AITokenUsageResponse, AITokenUsageSummaryResponse
from contractai_backend.modules.audit.application.services import AITokenTrackingService
from contractai_backend.modules.audit.domain.value_objs import AITokenSource
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import CurrentUserDep

router = APIRouter()


@router.get(path="/ai-usage", response_model=Sequence[AITokenUsageResponse])
async def list_ai_token_usage(
    service: Annotated[AITokenTrackingService, Depends(get_ai_token_tracking_service)],
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_id: Annotated[int | None, Query()] = None,
    source: Annotated[AITokenSource | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
) -> Sequence[AITokenUsageResponse]:
    """Lists AI token usage audit records for the current admin's organization, with optional filters by user, source, or date range."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Solo los administradores pueden consultar la auditoria de tokens")

    records = await service.list_usage(
        organization_id=current_user.organization_id,
        limit=limit,
        offset=offset,
        actor_user_id=user_id,
        source=source,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        AITokenUsageResponse(
            id=record.id or 0,
            organization_id=record.organization_id,
            actor_user_id=record.actor_user_id,
            source=record.source,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            input_cost_usd=float(record.input_cost_usd) if record.input_cost_usd is not None else None,
            output_cost_usd=float(record.output_cost_usd) if record.output_cost_usd is not None else None,
            total_cost_usd=float(record.total_cost_usd) if record.total_cost_usd is not None else None,
            model_used=record.model_used,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get(path="/ai-usage/summary", response_model=AITokenUsageSummaryResponse)
async def get_ai_token_usage_summary(
    service: Annotated[AITokenTrackingService, Depends(get_ai_token_tracking_service)],
    current_user: CurrentUserDep,
    user_id: Annotated[int | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
) -> AITokenUsageSummaryResponse:
    """Gets aggregated AI token usage stats (total tokens, total cost) at the organization or user level, optionally filtered by date range."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Solo los administradores pueden consultar la auditoria de tokens")

    summary = await service.get_summary(
        organization_id=current_user.organization_id,
        actor_user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return AITokenUsageSummaryResponse(
        total_tokens=summary["total_tokens"],
        total_cost_usd=summary["total_cost_usd"],
        input_tokens=summary["input_tokens"],
        output_tokens=summary["output_tokens"],
    )
