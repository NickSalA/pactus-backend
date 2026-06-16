"""Tests for contract activity audit router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.audit.api.dependencies import get_contract_activity_service
from contractai_backend.modules.audit.api.routers.contract_activity_router import router
from contractai_backend.modules.audit.domain.entities import ContractActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditContractAction
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/audit")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_contract_activity_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=10,
        email="admin@example.com",
        full_name="Admin User",
        role=role,
        is_active=True,
    )
    return app


def _make_activity() -> ContractActivityTable:
    return ContractActivityTable(
        id=1,
        organization_id=10,
        actor_user_id=1,
        actor_name="Admin User",
        actor_role="ADMIN",
        action=AuditContractAction.CREATED,
        document_id=100,
        document_name="contrato.pdf",
        document_type="COMPANY",
        state="ACTIVE",
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
    )


class TestContractActivityRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_own_organization_contract_activity(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=25&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action"] == "CREATED"
        assert data[0]["document_name"] == "contrato.pdf"
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=25, offset=5)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_contract_activity(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts")

        assert response.status_code == 403
        assert response.json()["type"] == "ForbiddenError"
        service.list_by_organization.assert_not_awaited()
