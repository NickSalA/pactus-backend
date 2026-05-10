"""Access rules for executive dashboard data."""

from ....core.exceptions.base import ForbiddenError
from ...documents.domain.value_objs import DocumentType
from ...users.domain.entities import UserTable
from ...users.domain.value_objs import UserRole

ALLOWED_DASHBOARD_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.MANAGER: frozenset({DocumentType.COMPANY}),
    UserRole.HR: frozenset({DocumentType.LABOR}),
}


def ensure_dashboard_access(current_user: UserTable, document_type: DocumentType) -> None:
    """Allow only MANAGER for COMPANY and HR for LABOR dashboard data."""
    allowed_types = ALLOWED_DASHBOARD_TYPES_BY_ROLE.get(current_user.role, frozenset())
    if document_type not in allowed_types:
        raise ForbiddenError("No tienes permisos para acceder a este dashboard")
