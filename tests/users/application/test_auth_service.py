"""Tests unitarios para AuthService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.users.application.dto.auth_dto import ExternalUserDTO
from contractai_backend.modules.users.application.services.auth_service import AuthService
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_external_user(**kwargs) -> ExternalUserDTO:
    defaults = {"id": uuid4(), "email": "user@example.com", "full_name": "Test User", "avatar_url": None}
    defaults.update(kwargs)
    return ExternalUserDTO(**defaults)


def _make_db_user(**kwargs) -> UserTable:
    defaults = {"id": 1, "organization_id": 1, "email": "user@example.com", "is_active": True, "role": UserRole.WORKER}
    defaults.update(kwargs)
    return UserTable(**defaults)


def _make_service(jwt_service=None, repo=None) -> AuthService:
    return AuthService(jwt_service=jwt_service or AsyncMock(), repo=repo or AsyncMock())


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_returns_existing_active_user(self):
        ext_user = _make_external_user(full_name="Test User")
        db_user = _make_db_user(supabase_user_id=ext_user.id, full_name="Test User")

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = db_user

        service = _make_service(jwt, repo)
        result = await service.authenticate_user("token")

        assert result == db_user
        repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_user_when_not_found(self):
        ext_user = _make_external_user(full_name="Test User")
        new_user = _make_db_user(supabase_user_id=ext_user.id, full_name="Test User")

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = None
        repo.save.return_value = new_user

        service = _make_service(jwt, repo)
        result = await service.authenticate_user("token")

        repo.save.assert_called_once()
        assert result == new_user

    @pytest.mark.asyncio
    async def test_inactive_user_raises_forbidden(self):
        ext_user = _make_external_user()
        db_user = _make_db_user(is_active=False)

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = db_user

        service = _make_service(jwt, repo)
        with pytest.raises(ForbiddenError):
            await service.authenticate_user("token")

    @pytest.mark.asyncio
    async def test_updates_supabase_id_when_missing(self):
        ext_user = _make_external_user()
        db_user = _make_db_user(supabase_user_id=None)
        updated_user = _make_db_user(supabase_user_id=ext_user.id)

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = db_user
        repo.update.return_value = updated_user

        service = _make_service(jwt, repo)
        result = await service.authenticate_user("token")

        repo.update.assert_called_once()
        assert result == updated_user

    @pytest.mark.asyncio
    async def test_updates_full_name_when_changed(self):
        ext_user = _make_external_user(full_name="New Name")
        db_user = _make_db_user(full_name="Old Name", supabase_user_id=ext_user.id)
        updated_user = _make_db_user(full_name="New Name", supabase_user_id=ext_user.id)

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = db_user
        repo.update.return_value = updated_user

        service = _make_service(jwt, repo)
        result = await service.authenticate_user("token")

        repo.update.assert_called_once()
        assert result.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_no_update_when_data_unchanged(self):
        uid = uuid4()
        ext_user = _make_external_user(id=uid, full_name="Same Name")
        db_user = _make_db_user(full_name="Same Name", supabase_user_id=uid)

        jwt = AsyncMock()
        jwt.get_authenticated_user.return_value = ext_user
        repo = AsyncMock()
        repo.get_by_email.return_value = db_user

        service = _make_service(jwt, repo)
        await service.authenticate_user("token")

        repo.update.assert_not_called()
