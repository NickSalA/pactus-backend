"""Value objects for the Documents domain."""

from enum import StrEnum


class DocumentType(StrEnum):
    """Tipos de documento permitidos por la base de datos."""

    COMPANY = "COMPANY"
    LABOR = "LABOR"


class DocumentState(StrEnum):
    """Estados de documento permitidos por la base de datos."""

    DRAFT = "DRAFT"
    PENDING_SIGNATURE = "PENDING_SIGNATURE"
    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


class CurrencyType(StrEnum):
    """Monedas permitidas para los servicios asociados a un documento."""

    PEN = "PEN"
    USD = "USD"
    EUR = "EUR"
