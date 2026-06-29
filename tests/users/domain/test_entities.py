"""Tests para entidades del dominio de usuarios."""

from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole


def test_user_default_role_is_worker():
    user = UserTable(organization_id=1, email="user@example.com")
    assert user.role == UserRole.WORKER


def test_user_default_is_active():
    user = UserTable(organization_id=1, email="user@example.com")
    assert user.is_active is True


def test_user_all_roles_accepted():
    for role in UserRole:
        user = UserTable(organization_id=1, email="user@example.com", role=role)
        assert user.role == role


def test_user_optional_fields_default_none():
    user = UserTable(organization_id=1, email="user@example.com")
    assert user.full_name is None
    assert user.avatar_url is None
    assert user.supabase_user_id is None
