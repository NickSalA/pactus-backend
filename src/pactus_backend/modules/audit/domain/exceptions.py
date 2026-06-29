"""Exceptions for the audit module."""

from ....core.exceptions.base import TooManyRequestsError


class LLMQuotaExceededError(TooManyRequestsError):
    def __init__(self, message: str = "Se ha excedido la cuota de peticiones al modelo de lenguaje."):
        super().__init__(message)
