"""HTTP schemas for billing."""

from ....modules.billing.application.dto import (
    ConfirmPayPalSubscriptionRequest as ApplicationConfirmPayPalSubscriptionRequest,
)
from ....modules.billing.application.dto import (
    ConfirmPayPalSubscriptionResponse as ApplicationConfirmPayPalSubscriptionResponse,
)


class ConfirmPayPalSubscriptionRequest(ApplicationConfirmPayPalSubscriptionRequest):
    """Request body for confirming a PayPal subscription."""


class ConfirmPayPalSubscriptionResponse(ApplicationConfirmPayPalSubscriptionResponse):
    """Response body for confirmed PayPal subscriptions."""


__all__ = ["ConfirmPayPalSubscriptionRequest", "ConfirmPayPalSubscriptionResponse"]
