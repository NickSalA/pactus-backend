"""Unit tests for DashboardService."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.dashboard.application.repositories import DashboardContractSummary, DashboardMonthlyAmount
from contractai_backend.modules.dashboard.application.services import ALERT_PREVIEW_LIMIT, RECENT_CONTRACTS_LIMIT, TOP_RANKING_LIMIT, DashboardService
from contractai_backend.modules.documents.domain.value_objs import DocumentType
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def _make_service(repo=None) -> DashboardService:
    return DashboardService(repository=repo or AsyncMock())


class TestDashboardAccess:
    @pytest.mark.asyncio
    async def test_manager_can_access_company_dashboard(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=date.today().replace(day=1), amount=1000)]
        service = _make_service(repo)

        response = await service.get_area_chart(current_user=_make_user(UserRole.MANAGER), document_type=DocumentType.COMPANY)

        assert response.props.title == "Ingresos Proyectados"

    @pytest.mark.asyncio
    async def test_hr_can_access_labor_dashboard(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.get_monthly_amounts.return_value = [DashboardMonthlyAmount(month=date.today().replace(day=1), amount=1000)]
        service = _make_service(repo)

        response = await service.get_area_chart(current_user=_make_user(UserRole.HR), document_type=DocumentType.LABOR)

        assert response.props.title == "Gasto de Planilla"

    @pytest.mark.asyncio
    async def test_admin_is_forbidden(self):
        service = _make_service()

        with pytest.raises(ForbiddenError):
            await service.get_area_chart(current_user=_make_user(UserRole.ADMIN), document_type=DocumentType.COMPANY)

    @pytest.mark.asyncio
    async def test_worker_is_forbidden(self):
        service = _make_service()

        with pytest.raises(ForbiddenError):
            await service.get_area_chart(current_user=_make_user(UserRole.WORKER), document_type=DocumentType.COMPANY)


class TestDashboardLimits:
    @pytest.mark.asyncio
    async def test_recent_contracts_uses_limit_four(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.list_recent_contracts.return_value = [
            DashboardContractSummary(id=1, title="Contrato", name="TechCorp", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        ]
        service = _make_service(repo)

        response = await service.get_recent_contracts(current_user=_make_user(UserRole.MANAGER), document_type=DocumentType.COMPANY)

        assert len(response) == 1
        repo.list_recent_contracts.assert_awaited_once_with(organization_id=10, document_type=DocumentType.COMPANY, limit=RECENT_CONTRACTS_LIMIT)

    @pytest.mark.asyncio
    async def test_top_companies_uses_limit_five(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.list_top_companies.return_value = []
        service = _make_service(repo)

        await service.get_top_companies(current_user=_make_user(UserRole.MANAGER))

        repo.list_top_companies.assert_awaited_once_with(organization_id=10, limit=TOP_RANKING_LIMIT)

    @pytest.mark.asyncio
    async def test_alert_center_uses_preview_limit_three(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.count_contracts_due_between.return_value = 0
        repo.count_long_term_contracts.return_value = 0
        repo.list_contracts_due_between.return_value = []
        repo.list_long_term_contracts.return_value = []
        service = _make_service(repo)

        await service.get_alert_center(current_user=_make_user(UserRole.HR), document_type=DocumentType.LABOR)

        assert repo.list_contracts_due_between.await_args_list[0].args[-1] == ALERT_PREVIEW_LIMIT
        assert repo.list_long_term_contracts.await_args.args[-1] == ALERT_PREVIEW_LIMIT
