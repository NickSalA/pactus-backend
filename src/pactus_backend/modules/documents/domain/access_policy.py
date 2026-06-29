"""Role-based access helpers for document operations."""

from collections.abc import Callable, Sequence
from typing import TypeVar

from ...users.domain.value_objs import UserRole
from .value_objs import DocumentType

T = TypeVar("T")

READABLE_DOCUMENT_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.HR: frozenset({DocumentType.LABOR}),
    UserRole.MANAGER: frozenset({DocumentType.COMPANY}),
    UserRole.WORKER: frozenset({DocumentType.COMPANY}),
}

WRITABLE_DOCUMENT_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.HR: frozenset({DocumentType.LABOR}),
    UserRole.MANAGER: frozenset({DocumentType.COMPANY}),
    UserRole.WORKER: frozenset(),
}

READABLE_FOLDER_OWNER_ROLES_BY_ROLE: dict[UserRole, frozenset[UserRole]] = {
    UserRole.HR: frozenset({UserRole.HR}),
    UserRole.MANAGER: frozenset({UserRole.MANAGER}),
    UserRole.WORKER: frozenset({UserRole.MANAGER}),
}

WRITABLE_FOLDER_OWNER_ROLES_BY_ROLE: dict[UserRole, frozenset[UserRole]] = {
    UserRole.HR: frozenset({UserRole.HR}),
    UserRole.MANAGER: frozenset({UserRole.MANAGER}),
    UserRole.WORKER: frozenset(),
}


def get_readable_document_types(user_role: UserRole | None) -> frozenset[DocumentType] | None:
    """Returns readable document types for the role, or None when unrestricted."""
    if user_role is None:
        return None

    return READABLE_DOCUMENT_TYPES_BY_ROLE.get(user_role)


def can_read_document_type(user_role: UserRole | None, document_type: DocumentType) -> bool:
    """Returns whether the role can read the given document type."""
    if user_role is None:
        return True
    allowed_types = READABLE_DOCUMENT_TYPES_BY_ROLE.get(user_role)
    return allowed_types is None or document_type in allowed_types


def can_write_document_type(user_role: UserRole | None, document_type: DocumentType) -> bool:
    """Returns whether the role can create, update or delete the given type."""
    if user_role is None:
        return True
    allowed_types = WRITABLE_DOCUMENT_TYPES_BY_ROLE.get(user_role)
    return allowed_types is None or document_type in allowed_types


FOLDER_CREATOR_ROLES: frozenset[UserRole] = frozenset({UserRole.HR, UserRole.MANAGER})


def can_create_folder(user_role: UserRole | None) -> bool:
    """Returns whether the role can create folders."""
    return user_role in FOLDER_CREATOR_ROLES


def can_read_folder(user_role: UserRole | None, owner_role: UserRole) -> bool:
    """Returns whether the role can list or inspect a folder owned by another role group."""
    if user_role is None:
        return True
    allowed_owner_roles = READABLE_FOLDER_OWNER_ROLES_BY_ROLE.get(user_role)
    return allowed_owner_roles is None or owner_role in allowed_owner_roles


def can_manage_folder(user_role: UserRole | None, owner_role: UserRole) -> bool:
    """Returns whether the role can update or delete a folder."""
    if user_role is None:
        return True
    allowed_owner_roles = WRITABLE_FOLDER_OWNER_ROLES_BY_ROLE.get(user_role)
    return allowed_owner_roles is None or owner_role in allowed_owner_roles


def filter_readable_documents[T](
    documents: Sequence[T],
    user_role: UserRole | None,
    get_document_type: Callable[[T], DocumentType],
) -> list[T]:
    """Returns only documents visible to the provided role."""
    if user_role is None or user_role not in READABLE_DOCUMENT_TYPES_BY_ROLE:
        return list(documents)

    return [document for document in documents if can_read_document_type(user_role, get_document_type(document))]
