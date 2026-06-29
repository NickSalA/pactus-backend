"""Unit tests for Dashboard Retention and Contract Origin services."""

from unittest.mock import AsyncMock

import pytest

from pactus_backend.core.exceptions.base import ForbiddenError
from pactus_backend.modules.dashboard.application.services import DashboardService
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def _make_service(repo=None) -> DashboardService:
    return DashboardService(repository=repo or AsyncMock())


class TestDashboardRetention:
    @pytest.mark.asyncio
    async def test_hr_can_access_retention_dashboard(self):
        repo = AsyncMock()
        repo.sync_contract_states.return_value = 0
        repo.get_retention_kpi_data.return_value = {
            "active_retention_rate": 85.5,
            "total_unique_workers": 12,
            "avg_contracts_per_worker": 2.4,
        }
        repo.get_tenure_distribution.return_value = [
            {"contracts_count": 1, "workers_count": 5},
            {"contracts_count": 2, "workers_count": 4},
            {"contracts_count": 3, "workers_count": 2},
            {"contracts_count": 4, "workers_count": 1},
        ]
        repo.get_monthly_renewal_trend.return_value = [{"month": "Ene 26", "renewal_rate": 80.0, "total_expired": 5, "total_renewed": 4}]
        repo.get_worker_retention_details.return_value = [
            {
                "worker_name": "John Doe",
                "worker_document_number": "12345678",
                "contracts_count": 3,
                "first_contract_start": "2025-01-01",
                "latest_contract_end": "2026-06-30",
            }
        ]

        service = _make_service(repo)
        response = await service.get_labor_retention_dashboard(current_user=_make_user(UserRole.HR))

        # Assert DTO properties are mapped correctly
        assert response.kpis.active_retention_rate == 85.5
        assert response.kpis.total_unique_workers == 12
        assert response.kpis.avg_contracts_per_worker == 2.4

        assert len(response.tenure_distribution) == 4
        assert response.tenure_distribution[0].contracts_count == 1
        assert response.tenure_distribution[0].workers_count == 5

        assert len(response.renewal_trend) == 1
        assert response.renewal_trend[0].month == "Ene 26"
        assert response.renewal_trend[0].renewal_rate == 80.0

        assert len(response.details) == 1
        assert response.details[0].worker_name == "John Doe"
        assert response.details[0].worker_document_number == "12345678"

        # Assert infrastructure is triggered properly
        repo.sync_contract_states.assert_awaited_once_with(organization_id=10)
        repo.get_retention_kpi_data.assert_awaited_once_with(organization_id=10)

    @pytest.mark.asyncio
    async def test_non_hr_cannot_access_retention_dashboard(self):
        service = _make_service()
        non_hr_roles = [UserRole.MANAGER, UserRole.WORKER, UserRole.ADMIN]

        for role in non_hr_roles:
            with pytest.raises(ForbiddenError):
                await service.get_labor_retention_dashboard(current_user=_make_user(role))


class TestDashboardOrigin:
    @pytest.mark.asyncio
    async def test_hr_can_access_origin_dashboard(self):
        repo = AsyncMock()
        repo.get_contract_origin_distribution.return_value = [
            {"origin_type": "Plantilla: Plazo Fijo", "count": 10, "percentage": 50.0},
            {"origin_type": "Carga Manual", "count": 8, "percentage": 40.0},
            {"origin_type": "Importación: Google Drive", "count": 2, "percentage": 10.0},
        ]

        service = _make_service(repo)
        response = await service.get_labor_origin_dashboard(current_user=_make_user(UserRole.HR))

        assert response.total_contracts == 20
        assert len(response.distribution) == 3
        assert response.distribution[0].origin_type == "Plantilla: Plazo Fijo"
        assert response.distribution[0].count == 10
        assert response.distribution[0].percentage == 50.0

        repo.get_contract_origin_distribution.assert_awaited_once_with(organization_id=10)

    @pytest.mark.asyncio
    async def test_non_hr_cannot_access_origin_dashboard(self):
        service = _make_service()
        non_hr_roles = [UserRole.MANAGER, UserRole.WORKER, UserRole.ADMIN]

        for role in non_hr_roles:
            with pytest.raises(ForbiddenError):
                await service.get_labor_origin_dashboard(current_user=_make_user(role))
