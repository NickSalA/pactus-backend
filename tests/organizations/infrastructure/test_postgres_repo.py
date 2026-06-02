"""Tests unitarios para SQLModelOrganizationRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.organizations.infrastructure.postgres_repo import SQLModelOrganizationRepository


def _make_org(id: int = 1) -> OrganizationTable:
    return OrganizationTable(id=id, name="Org Test", is_active=True)


def _make_repo() -> tuple[SQLModelOrganizationRepository, AsyncMock]:
    session = AsyncMock()
    repo = SQLModelOrganizationRepository(session=session)
    return repo, session


class TestGetByName:
    @pytest.mark.asyncio
    async def test_returns_organization_by_name(self):
        org = _make_org()
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.first.return_value = org
        session.exec.return_value = result_mock

        result = await repo.get_by_name("org test")
        assert result == org

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        result = await repo.get_by_name("desconocida")
        assert result is None


class TestGetByRuc:
    @pytest.mark.asyncio
    async def test_returns_organization_by_ruc(self):
        org = _make_org()
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.first.return_value = org
        session.exec.return_value = result_mock

        result = await repo.get_by_ruc("123456789")
        assert result == org

    @pytest.mark.asyncio
    async def test_returns_none_when_ruc_not_found(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        result = await repo.get_by_ruc("000000000")
        assert result is None


class TestGetAll:
    @pytest.mark.asyncio
    async def test_returns_active_organizations(self):
        orgs = [_make_org(1), _make_org(2)]
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = orgs
        session.exec.return_value = result_mock

        result = await repo.get_all(filters={"is_active": True})
        assert result == orgs

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        result = await repo.get_all(filters={"is_active": True})
        assert result == []
