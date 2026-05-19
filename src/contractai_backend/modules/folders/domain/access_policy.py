"""Role-based access helpers for folder operations."""

from ...users.domain.value_objs import UserRole

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
