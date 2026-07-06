"""HTTP routes for billing workflows."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ....modules.billing.api.dependencies import get_paypal_subscription_service
from ....modules.billing.api.schemas import ConfirmPayPalSubscriptionRequest, ConfirmPayPalSubscriptionResponse
from ....modules.billing.application.services import PayPalSubscriptionService

router = APIRouter(prefix="/paypal")


@router.post(
    path="/subscriptions/confirm",
    response_model=ConfirmPayPalSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_paypal_subscription(
    payload: ConfirmPayPalSubscriptionRequest,
    service: Annotated[PayPalSubscriptionService, Depends(get_paypal_subscription_service)],
) -> ConfirmPayPalSubscriptionResponse:
    """Confirms a PayPal subscription and provisions the initial organization admin."""
    result = await service.confirm_subscription(payload)
    return ConfirmPayPalSubscriptionResponse.model_validate(result)
