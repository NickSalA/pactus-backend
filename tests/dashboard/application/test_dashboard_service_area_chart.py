"""Unit tests for dashboard area chart responses."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from pactus_backend.modules.dashboard.application.repositories import DashboardMonthlyAmount
from pactus_backend.modules.dashboard.application.services import AREA_CHART_FORECAST_MONTHS, AREA_CHART_HISTORY_MONTHS, DashboardService
from pactus_backend.modules.documents.domain.value_objs import CurrencyType, DocumentType
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole = UserRole.MANAGER) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _monthly_amounts(start_month: date, amounts: list[float]) -> list[DashboardMonthlyAmount]:
    return [DashboardMonthlyAmount(month=_add_months(start_month, index), amount=amount) for index, amount in enumerate(amounts)]


@pytest.mark.asyncio
async def test_area_chart_builds_historical_current_and_forecast_points():
    repo = AsyncMock()
    today_month = _month_start(date.today())
    start_month = _add_months(today_month, -AREA_CHART_HISTORY_MONTHS)
    repo.sync_contract_states.return_value = 0
    repo.get_monthly_amounts.return_value = _monthly_amounts(start_month, [100, 200, 300, 400, 500, 600, 700])
    service = DashboardService(repository=repo)

    response = await service.get_area_chart(current_user=_make_user(), document_type=DocumentType.COMPANY)

    points = response.props.series[0].data
    assert len(points) == AREA_CHART_HISTORY_MONTHS + 1 + AREA_CHART_FORECAST_MONTHS
    assert [point.y for point in points] == [100, 200, 300, 400, 500, 600, 700]
    assert [point.is_forecast for point in points] == [False, False, False, False, False, True, True]


@pytest.mark.asyncio
async def test_area_chart_passes_currency_filter_to_repository_and_response():
    repo = AsyncMock()
    current_month = _month_start(date.today())
    repo.sync_contract_states.return_value = 0
    repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=current_month, amount=1234.56)]
    service = DashboardService(repository=repo)

    response = await service.get_area_chart(current_user=_make_user(), document_type=DocumentType.COMPANY, currency=CurrencyType.PEN)

    repo.get_monthly_amounts.assert_awaited_once()
    assert repo.get_monthly_amounts.await_args.kwargs["currency"] == CurrencyType.PEN
    assert response.props.series[0].currency == CurrencyType.PEN


@pytest.mark.asyncio
async def test_area_chart_uses_all_currency_when_filter_is_absent():
    repo = AsyncMock()
    current_month = _month_start(date.today())
    repo.sync_contract_states.return_value = 0
    repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=current_month, amount=1000.0)]
    service = DashboardService(repository=repo)

    response = await service.get_area_chart(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert response.props.series[0].currency == "ALL"


@pytest.mark.asyncio
async def test_area_chart_builds_y_axis_labels_from_max_amount():
    repo = AsyncMock()
    current_month = _month_start(date.today())
    repo.sync_contract_states.return_value = 0
    repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=current_month, amount=4500.0)]
    service = DashboardService(repository=repo)

    response = await service.get_area_chart(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert response.props.y_axis.labels == [0.0, 2000.0, 4000.0, 6000.0, 8000.0]


@pytest.mark.asyncio
async def test_labor_area_chart_uses_labor_copy():
    repo = AsyncMock()
    current_month = _month_start(date.today())
    repo.sync_contract_states.return_value = 0
    repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=current_month, amount=1000.0)]
    service = DashboardService(repository=repo)

    response = await service.get_area_chart(current_user=_make_user(UserRole.HR), document_type=DocumentType.LABOR)

    assert response.props.title == "Gasto de Planilla"
    assert response.props.subtitle == "Costo historico y reduccion por fin de contratos"
    assert response.props.series[0].name == "Gasto"
