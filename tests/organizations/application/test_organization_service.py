"""Tests unitarios para OrganizationService."""

from unittest.mock import AsyncMock

import pytest

from pactus_backend.core.exceptions.base import NotFoundError
from pactus_backend.modules.organizations.application.services.organization_service import OrganizationService
from pactus_backend.modules.organizations.domain.entities import OrganizationTable


def _make_org(id: int = 1, is_active: bool = True) -> OrganizationTable:
    return OrganizationTable(id=id, name=f"Org {id}", is_active=is_active)


def _make_service(repo=None) -> OrganizationService:
    return OrganizationService(repository=repo or AsyncMock())


class TestListOrganizations:
    @pytest.mark.asyncio
    async def test_returns_all_organizations(self):
        orgs = [_make_org(1), _make_org(2)]
        repo = AsyncMock()
        repo.get_all.return_value = orgs

        service = _make_service(repo)
        result = await service.list_organizations()

        assert result == orgs
        repo.get_all.assert_awaited_once_with(filters=None, limit=None, offset=None)

    @pytest.mark.asyncio
    async def test_returns_active_only(self):
        orgs = [_make_org(1)]
        repo = AsyncMock()
        repo.get_all.return_value = orgs

        service = _make_service(repo)
        result = await service.list_organizations(is_active=True)

        assert result == orgs
        repo.get_all.assert_awaited_once_with(filters={"is_active": True}, limit=None, offset=None)


class TestGetOrganization:
    @pytest.mark.asyncio
    async def test_returns_organization(self):
        org = _make_org()
        repo = AsyncMock()
        repo.get_by_id.return_value = org

        service = _make_service(repo)
        result = await service.get_organization(1)

        assert result == org

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        repo = AsyncMock()
        repo.get_by_id.return_value = None

        service = _make_service(repo)
        with pytest.raises(NotFoundError):
            await service.get_organization(99)
