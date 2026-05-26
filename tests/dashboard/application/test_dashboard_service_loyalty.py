"""Unit tests for B2B Client Loyalty Dashboard services."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.dashboard.application.services import DashboardService
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def _make_service(repo=None) -> DashboardService:
    return DashboardService(repo or AsyncMock())


class TestDashboardCompanyLoyalty:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [UserRole.MANAGER, UserRole.WORKER])
    async def test_authorized_roles_can_access_loyalty_dashboard(self, role):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.get_company_loyalty_kpi_data.return_value = {
            "active_retention_rate": 75.0,
            "total_unique_clients": 8,
            "avg_contracts_per_client": 3.2,
        }
        repo.get_company_tenure_distribution.return_value = [
            {"contracts_count": 1, "clients_count": 2},
            {"contracts_count": 2, "clients_count": 3},
            {"contracts_count": 3, "clients_count": 2},
            {"contracts_count": 4, "clients_count": 1},
        ]
        repo.get_company_monthly_renewal_trend.return_value = [{"month": "Ene 26", "renewal_rate": 90.0, "total_expired": 10, "total_renewed": 9}]
        repo.get_company_loyalty_details.return_value = [
            {
                "client_name": "Acme Corp",
                "ruc": "20102030405",
                "contracts_count": 5,
                "first_contract_start": "2024-01-01",
                "latest_contract_end": "2026-12-31",
            }
        ]

        service = _make_service(repo)
        response = await service.get_company_loyalty_dashboard(current_user=_make_user(role))

        # Assert DTO properties are mapped correctly
        assert response.kpis.active_retention_rate == 75.0
        assert response.kpis.total_unique_clients == 8
        assert response.kpis.avg_contracts_per_client == 3.2

        assert len(response.tenure_distribution) == 4
        assert response.tenure_distribution[0].contracts_count == 1
        assert response.tenure_distribution[0].clients_count == 2

        assert len(response.renewal_trend) == 1
        assert response.renewal_trend[0].month == "Ene 26"
        assert response.renewal_trend[0].renewal_rate == 90.0

        assert len(response.details) == 1
        assert response.details[0].client_name == "Acme Corp"
        assert response.details[0].ruc == "20102030405"
        assert response.details[0].contracts_count == 5

        # Assert infrastructure is triggered properly
        repo.sync_contract_states.assert_awaited_once_with(organization_id=10)
        repo.get_company_loyalty_kpi_data.assert_awaited_once_with(organization_id=10)
        repo.get_company_tenure_distribution.assert_awaited_once_with(organization_id=10)
        repo.get_company_monthly_renewal_trend.assert_awaited_once_with(organization_id=10)
        repo.get_company_loyalty_details.assert_awaited_once_with(organization_id=10)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [UserRole.HR, UserRole.ADMIN])
    async def test_unauthorized_roles_cannot_access_loyalty_dashboard(self, role):
        service = _make_service()
        with pytest.raises(ForbiddenError):
            await service.get_company_loyalty_dashboard(current_user=_make_user(role))
