"""Shared access-control helpers used across modules."""

from ..exceptions.base import ForbiddenError
from ...modules.users.domain.entities import UserTable
from ...modules.users.domain.value_objs import UserRole


def ensure_admin(current_user: UserTable, message: str = "Solo los administradores pueden realizar esta acción") -> None:
    """Raises ForbiddenError when the user is not an ADMIN."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError(message)
