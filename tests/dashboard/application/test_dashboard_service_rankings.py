"""Unit tests for dashboard ranking responses."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.dashboard.application.repositories import DashboardClientRanking, DashboardServiceRanking
from contractai_backend.modules.dashboard.application.services import TOP_RANKING_LIMIT, DashboardService
from contractai_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from contractai_backend.modules.documents.domain.value_objs import CurrencyType
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_manager() -> UserTable:
    return UserTable(id=1, organization_id=10, email="manager@example.com", role=UserRole.MANAGER, is_active=True)


@pytest.mark.asyncio
async def test_top_companies_uses_volume_sort_by_default():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_companies.return_value = []
    service = DashboardService(repository=repo)

    await service.get_top_companies(current_user=_make_manager())

    repo.list_top_companies.assert_awaited_once_with(
        organization_id=10,
        limit=TOP_RANKING_LIMIT,
        currency=None,
        sort_by=TopRankingSortBy.VOLUME,
    )


@pytest.mark.asyncio
async def test_top_companies_passes_currency_and_value_sort():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_companies.return_value = []
    service = DashboardService(repository=repo)

    await service.get_top_companies(current_user=_make_manager(), currency=CurrencyType.USD, sort_by=TopRankingSortBy.VALUE)

    repo.list_top_companies.assert_awaited_once_with(
        organization_id=10,
        limit=TOP_RANKING_LIMIT,
        currency=CurrencyType.USD,
        sort_by=TopRankingSortBy.VALUE,
    )


@pytest.mark.asyncio
async def test_top_companies_serializes_and_rounds_amounts():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_companies.return_value = [DashboardClientRanking(name="TechCorp SA", contracts=5, amount=120000.456)]
    service = DashboardService(repository=repo)

    response = await service.get_top_companies(current_user=_make_manager())

    assert response[0].name == "TechCorp SA"
    assert response[0].contracts == 5
    assert response[0].amount == 120000.46


@pytest.mark.asyncio
async def test_top_services_uses_volume_sort_by_default():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_services.return_value = []
    service = DashboardService(repository=repo)

    await service.get_top_services(current_user=_make_manager())

    repo.list_top_services.assert_awaited_once_with(
        organization_id=10,
        limit=TOP_RANKING_LIMIT,
        currency=None,
        sort_by=TopRankingSortBy.VOLUME,
    )


@pytest.mark.asyncio
async def test_top_services_passes_currency_and_value_sort():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_services.return_value = []
    service = DashboardService(repository=repo)

    await service.get_top_services(current_user=_make_manager(), currency=CurrencyType.EUR, sort_by=TopRankingSortBy.VALUE)

    repo.list_top_services.assert_awaited_once_with(
        organization_id=10,
        limit=TOP_RANKING_LIMIT,
        currency=CurrencyType.EUR,
        sort_by=TopRankingSortBy.VALUE,
    )


@pytest.mark.asyncio
async def test_top_services_serializes_and_rounds_amounts():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.list_top_services.return_value = [DashboardServiceRanking(name="Cloud Support", quantity=7, amount=9900.555)]
    service = DashboardService(repository=repo)

    response = await service.get_top_services(current_user=_make_manager())

    assert response[0].name == "Cloud Support"
    assert response[0].quantity == 7
    assert response[0].amount == 9900.56
