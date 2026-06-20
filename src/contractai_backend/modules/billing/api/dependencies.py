"""Dependency providers for billing."""

from typing import Annotated

import httpx
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.billing.application.repositories import BillingProvisioningRepository, PayPalSubscriptionGateway
from contractai_backend.modules.billing.application.services import PayPalSubscriptionService
from contractai_backend.modules.billing.composition import build_paypal_subscription_service
from contractai_backend.modules.billing.infrastructure import PayPalSubscriptionAdapter, SQLModelBillingProvisioningRepository
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
