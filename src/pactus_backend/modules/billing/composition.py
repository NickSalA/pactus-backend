"""Composition helpers for the billing module."""

from .application.repositories import BillingProvisioningRepository, PayPalSubscriptionGateway
from .application.services import PayPalSubscriptionService


def build_paypal_subscription_service(
    paypal_gateway: PayPalSubscriptionGateway,
    provisioning_repository: BillingProvisioningRepository,
) -> PayPalSubscriptionService:
    """Builds the PayPal subscription confirmation service."""
    return PayPalSubscriptionService(paypal_gateway=paypal_gateway, provisioning_repository=provisioning_repository)
