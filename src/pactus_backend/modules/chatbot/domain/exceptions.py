"""Custom exceptions for chatbot module."""

from ....core.exceptions.base import (
    BadGatewayError,
    GatewayTimeoutError,
    InternalServerError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


class ChatbotValidationError(ValidationError):
    def __init__(self, message: str = "El mensaje enviado es inválido o está vacío."):
        super().__init__(message)


class ConversationNotFoundError(NotFoundError):
    def __init__(self, message: str = "La conversación solicitada no existe o no tienes acceso a ella."):
        super().__init__(message)


class ChatbotDatabaseUnavailableError(ServiceUnavailableError):
    def __init__(self, message: str = "El servicio de persistencia de mensajes no está disponible."):
        super().__init__(message)


class LLMInitializationError(InternalServerError):
    def __init__(self, message: str = "Error al inicializar el motor de inteligencia artificial."):
        super().__init__(message)


class LLMExecutionError(BadGatewayError):
    def __init__(self, message: str = "Error en la generación de la respuesta por parte del agente."):
        super().__init__(message)



class VectorDatabaseUnavailableError(ServiceUnavailableError):
    def __init__(self, message: str = "El motor de búsqueda vectorial no está accesible."):
        super().__init__(message)


class VectorSearchError(BadGatewayError):
    def __init__(self, message: str = "Error al recuperar fragmentos de la base de conocimientos."):
        super().__init__(message)


class ChatbotTimeoutError(GatewayTimeoutError):
    def __init__(self, message: str = "El agente ha excedido el tiempo de espera para responder."):
        super().__init__(message)


class ChatbotAgentError(InternalServerError):
    def __init__(self, message: str = "Error interno en el agente conversacional."):
        super().__init__(message)
