"""Tests for SQLModelUserRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from pactus_backend.core.exceptions.base import ServiceUnavailableError
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.infrastructure.postgres_repo import SQLModelUserRepository


def _make_repo() -> tuple[SQLModelUserRepository, AsyncMock]:
    session = AsyncMock()
    repo = SQLModelUserRepository(session=session)
    return repo, session


def _make_user() -> UserTable:
    return UserTable(
        id=1,
        organization_id=2,
        email="worker@example.com",
        full_name="Worker Test",
    )


class TestGetByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        user = _make_user()
        result_mock.first.return_value = user
        session.exec.return_value = result_mock

        result = await repo.get_by_email("worker@example.com")

        assert result == user
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_pool_timeout_raises_service_unavailable(self):
        repo, session = _make_repo()
        session.exec.side_effect = SQLAlchemyTimeoutError("QueuePool limit reached")

        with pytest.raises(ServiceUnavailableError):
            await repo.get_by_email("worker@example.com")
