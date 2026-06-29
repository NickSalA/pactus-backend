"""Excepciones personalizadas para el módulo de documentos."""

from ....core.exceptions.base import BadGatewayError, InternalServerError, NotFoundError, ServiceUnavailableError, ValidationError


class DocumentNotFoundError(NotFoundError):
    """Se lanza cuando un documento no existe en la base de datos."""

    def __init__(self, document_id: int):
        super().__init__(message=f"El documento con ID {document_id} no fue encontrado.")


class DocumentFileMissingError(NotFoundError):
    """Se lanza cuando se solicita un archivo físico de un documento que no lo tiene."""

    def __init__(self, document_id: int):
        super().__init__(message=f"El documento con ID {document_id} no tiene un archivo asociado.")


class InvalidDocumentFileError(ValidationError):
    """Se lanza cuando el archivo subido no tiene los metadatos requeridos (nombre o tipo)."""

    def __init__(self, message: str = "El nombre del archivo y el tipo de contenido son obligatorios."):
        super().__init__(message)


class DocumentValidationError(ValidationError):
    """Se lanza cuando los datos del documento no cumplen con las reglas de validación."""

    def __init__(self, message: str = "Los datos del documento son inválidos."):
        super().__init__(message)


class DocumentExtractionError(BadGatewayError):
    """Se lanza cuando LlamaParse o el extractor fallan al procesar el archivo."""

    def __init__(self, message: str = "Fallo al extraer los datos del documento."):
        super().__init__(message)


class DocumentTransactionError(InternalServerError):
    """Se lanza cuando falla la orquestación (Saga) entre SQL, Storage y VectorDB."""

    def __init__(self, operation: str, details: str):
        super().__init__(message=f"Falló la transacción de {operation} del documento: {details}")


class DocumentStorageError(BadGatewayError):
    """Se lanza cuando el proveedor de almacenamiento de archivos rechaza o falla en una operación."""

    def __init__(self, message: str = "Fallo en el proveedor de almacenamiento de documentos."):
        super().__init__(message)


class DocumentStorageUnavailableError(ServiceUnavailableError):
    """Se lanza cuando el proveedor de almacenamiento de archivos está inaccesible."""

    def __init__(self, message: str = "El servicio de almacenamiento de documentos no está disponible."):
        super().__init__(message)


class DocumentDatabaseUnavailableError(ServiceUnavailableError):
    """Se lanza cuando la base de datos relacional no está disponible para operaciones de documentos."""

    def __init__(self, message: str = "La base de datos relacional para documentos no está disponible."):
        super().__init__(message)


class DocumentDatabaseError(InternalServerError):
    """Se lanza cuando ocurre un error inesperado al acceder a la base de datos relacional para documentos."""

    def __init__(self, message: str = "Error al acceder a la base de datos relacional para documentos."):
        super().__init__(message)


class DocumentVectorError(BadGatewayError):
    """Se lanza cuando la base de datos vectorial rechaza o falla en una operación."""

    def __init__(self, message: str = "Fallo en el motor de búsqueda vectorial."):
        super().__init__(message)


class DocumentVectorUnavailableError(ServiceUnavailableError):
    """Se lanza cuando la base de datos vectorial está inaccesible o hay timeout."""

    def __init__(self, message: str = "El servicio de búsqueda vectorial no está disponible."):
        super().__init__(message)
