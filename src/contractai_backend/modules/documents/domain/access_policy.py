"""Role-based access helpers for document operations."""

from collections.abc import Callable, Sequence
from typing import TypeVar

from ...users.domain.value_objs import UserRole
from .value_objs import DocumentType

T = TypeVar("T")

READABLE_DOCUMENT_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.HR: frozenset({DocumentType.LABOR}),
    UserRole.WORKER: frozenset({DocumentType.COMPANY}),
}

WRITABLE_DOCUMENT_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.HR: frozenset({DocumentType.LABOR}),
    UserRole.WORKER: frozenset(),
}


def can_read_document_type(user_role: UserRole | None, document_type: DocumentType) -> bool:
    """Returns whether the role can read the given document type."""
    allowed_types = READABLE_DOCUMENT_TYPES_BY_ROLE.get(user_role)
    return allowed_types is None or document_type in allowed_types


def can_write_document_type(user_role: UserRole | None, document_type: DocumentType) -> bool:
    """Returns whether the role can create, update or delete the given type."""
    allowed_types = WRITABLE_DOCUMENT_TYPES_BY_ROLE.get(user_role)
    return allowed_types is None or document_type in allowed_types


def filter_readable_documents(
    documents: Sequence[T],
    user_role: UserRole | None,
    get_document_type: Callable[[T], DocumentType],
) -> list[T]:
    """Returns only documents visible to the provided role."""
    if user_role is None or user_role not in READABLE_DOCUMENT_TYPES_BY_ROLE:
        return list(documents)

    return [document for document in documents if can_read_document_type(user_role, get_document_type(document))]
