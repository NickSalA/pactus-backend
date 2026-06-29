"""Application DTOs for billing workflows."""

import re

from pydantic import BaseModel, ConfigDict, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PAYPAL_SUBSCRIPTION_RE = re.compile(r"^[A-Za-z0-9_-]{6,128}$")


class ConfirmPayPalSubscriptionRequest(BaseModel):
    """Input used to confirm a PayPal subscription after checkout approval."""

    subscription_id: str
    email: str

    @field_validator("subscription_id")
    @classmethod
    def validate_subscription_id(cls, value: str) -> str:
        normalized = value.strip()
        if not PAYPAL_SUBSCRIPTION_RE.fullmatch(normalized):
            raise ValueError("El ID de suscripción de PayPal no es válido")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            raise ValueError("El correo no es válido")
        return normalized


class ConfirmPayPalSubscriptionResponse(BaseModel):
    """Response returned after provisioning the subscribed organization."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: int
    admin_email: str
    paypal_subscription_id: str


class PayPalSubscriptionDetails(BaseModel):
    """Normalized PayPal subscription data required by the application layer."""

    id: str
    custom_id: str
