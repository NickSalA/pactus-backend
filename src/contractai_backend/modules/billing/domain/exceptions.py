"""Domain errors for billing workflows."""

from contractai_backend.core.exceptions.base import BadGatewayError, ConflictError, ValidationError


class PayPalSubscriptionValidationError(ValidationError):
    """Raised when PayPal subscription data cannot be accepted."""

    def __init__(self, message: str = "La suscripción de PayPal no es válida."):
        super().__init__(message=message)


class PayPalSubscriptionConflictError(ConflictError):
    """Raised when a PayPal subscription cannot be provisioned due to existing data."""

    def __init__(self, message: str = "La suscripción de PayPal ya fue registrada."):
        super().__init__(message=message)


class PayPalServiceError(BadGatewayError):
    """Raised when PayPal returns an unexpected response."""

    def __init__(self, message: str = "PayPal devolvió una respuesta inesperada."):
        super().__init__(message=message)
