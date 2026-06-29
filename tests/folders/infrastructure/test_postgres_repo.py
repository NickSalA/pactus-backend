"""Tests for SQLModelFolderRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pactus_backend.modules.folders.domain.entities import FolderTable
from pactus_backend.modules.folders.infrastructure.postgres_repo import SQLModelFolderRepository
from pactus_backend.modules.users.domain.value_objs import UserRole


def _make_repo() -> tuple[SQLModelFolderRepository, AsyncMock]:
    session = AsyncMock()
    repo = SQLModelFolderRepository(session=session)
    return repo, session


class TestGetAll:
    @pytest.mark.asyncio
    async def test_orders_by_id_before_pagination(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = [
            FolderTable(id=1, organization_id=1, name="A", owner_role=UserRole.MANAGER, created_by=1)
        ]
        session.exec.return_value = result_mock

        await repo.get_all(filters={"organization_id": 1}, limit=10, offset=20)

        statement = session.exec.await_args.kwargs["statement"]
        statement_sql = str(statement)

        assert "ORDER BY" in statement_sql
        assert "document_folders.id" in statement_sql
        assert "LIMIT" in statement_sql
        assert "OFFSET" in statement_sql
