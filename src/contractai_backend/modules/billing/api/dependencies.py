"""Dependency providers for billing."""

from typing import Annotated

import httpx
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.billing.application.repositories import BillingProvisioningRepository, PayPalSubscriptionGateway
from contractai_backend.modules.billing.application.services import PayPalSubscriptionService
from contractai_backend.modules.billing.composition import build_paypal_subscription_service
from contractai_backend.modules.billing.infrastructure import PayPalSubscriptionAdapter, SQLModelBillingProvisioningRepository
from contractai_backend.shared.api.dependencies.security import CurrentUserDep
from contractai_backend.shared.config import settings
from contractai_backend.shared.infrastructure.database import get_session
from contractai_backend.shared.infrastructure.http import get_http_client


async def get_billing_provisioning_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> BillingProvisioningRepository:
    """Provide the billing provisioning repository."""
    return SQLModelBillingProvisioningRepository(session=session)


async def get_paypal_subscription_gateway(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]) -> PayPalSubscriptionGateway:
    """Provide the PayPal subscription gateway."""
    return PayPalSubscriptionAdapter(
        client=client,
        client_id=settings.PAYPAL_CLIENT_ID,
        client_secret=settings.PAYPAL_CLIENT_SECRET,
        base_url=settings.PAYPAL_BASE_URL,
    )


async def get_paypal_subscription_service(
    paypal_gateway: Annotated[PayPalSubscriptionGateway, Depends(get_paypal_subscription_gateway)],
    provisioning_repository: Annotated[BillingProvisioningRepository, Depends(get_billing_provisioning_repository)],
) -> PayPalSubscriptionService:
    """Provide the PayPal subscription application service."""
    return build_paypal_subscription_service(paypal_gateway=paypal_gateway, provisioning_repository=provisioning_repository)


async def require_active_subscription(
    current_user: CurrentUserDep,
    subscription_service: Annotated[PayPalSubscriptionService, Depends(get_paypal_subscription_service)],
) -> None:
    """FastAPI dependency that blocks the request if the user's organization has no active subscription."""
    if not await subscription_service.check_subscription_active(current_user.organization_id):
        raise ForbiddenError("Suscripción no activa. Contacta con el administrador de tu organización.")
