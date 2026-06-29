"""Tests for contract activity audit router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pactus_backend.core.exceptions.base import AppError
from pactus_backend.modules.audit.api.dependencies import get_contract_activity_service
from pactus_backend.modules.audit.api.routers.contract_activity_router import router
from pactus_backend.modules.audit.domain.entities import ContractActivityTable
from pactus_backend.modules.audit.domain.value_objs import AuditContractAction
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole
from pactus_backend.shared.api.dependencies.security import get_current_user
from pactus_backend.shared.api.error_handlers import app_error_handler


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


def _make_activity(
    *,
    id: int = 1,
    action: AuditContractAction = AuditContractAction.MANUAL_UPLOAD,
    document_id: int | None = 100,
    company_contract_id: int | None = None,
    labor_contract_id: int | None = None,
    document_name: str | None = "contrato.pdf",
    document_type: str | None = "COMPANY",
    previous_state: str | None = None,
    state: str | None = "ACTIVE",
    created_at: datetime = datetime(2026, 6, 8, tzinfo=UTC),
) -> ContractActivityTable:
    return ContractActivityTable(
        id=id,
        organization_id=10,
        actor_user_id=1,
        actor_name="Admin User",
        actor_role="ADMIN",
        action=action,
        document_id=document_id,
        company_contract_id=company_contract_id,
        labor_contract_id=labor_contract_id,
        document_name=document_name,
        document_type=document_type,
        previous_state=previous_state,
        state=state,
        created_at=created_at,
    )


def _expected_activity_payload() -> dict:
    return {
        "id": 1,
        "organization_id": 10,
        "actor_user_id": 1,
        "actor_name": "Admin User",
        "actor_role": "ADMIN",
        "action": "MANUAL_UPLOAD",
        "document_id": 100,
        "company_contract_id": None,
        "labor_contract_id": None,
        "document_name": "contrato.pdf",
        "document_type": "COMPANY",
        "previous_state": None,
        "state": "ACTIVE",
        "created_at": "2026-06-08T00:00:00Z",
    }


class TestContractActivityRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_own_organization_contract_activity(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=25&offset=5")

        assert response.status_code == 200
        assert response.json() == [_expected_activity_payload()]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=25, offset=5)

    @pytest.mark.asyncio
    async def test_admin_lists_multiple_contract_activity_types_without_mixing_fields(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [
            _make_activity(id=1, company_contract_id=501, document_name="empresa.pdf", document_type="COMPANY"),
            _make_activity(
                id=2,
                action=AuditContractAction.UPDATED,
                document_id=200,
                labor_contract_id=701,
                document_name="laboral.pdf",
                document_type="LABOR",
                previous_state="DRAFT",
                state="ACTIVE",
                created_at=datetime(2026, 6, 9, tzinfo=UTC),
            ),
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=100&offset=0")

        assert response.status_code == 200
        assert response.json() == [
            {
                **_expected_activity_payload(),
                "company_contract_id": 501,
                "document_name": "empresa.pdf",
            },
            {
                **_expected_activity_payload(),
                "id": 2,
                "action": "UPDATED",
                "document_id": 200,
                "labor_contract_id": 701,
                "document_name": "laboral.pdf",
                "document_type": "LABOR",
                "previous_state": "DRAFT",
                "created_at": "2026-06-09T00:00:00Z",
            },
        ]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_admin_lists_contract_activity_with_nullable_panel_fields(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [
            _make_activity(
                action=AuditContractAction.DELETED,
                document_id=None,
                company_contract_id=None,
                labor_contract_id=None,
                document_name=None,
                document_type=None,
                previous_state="ACTIVE",
                state=None,
            )
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts")

        assert response.status_code == 200
        assert response.json() == [
            {
                **_expected_activity_payload(),
                "action": "DELETED",
                "document_id": None,
                "document_name": None,
                "document_type": None,
                "previous_state": "ACTIVE",
                "state": None,
            }
        ]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_admin_lists_empty_contract_activity_with_default_pagination(self):
        service = AsyncMock()
        service.list_by_organization.return_value = []
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts")

        assert response.status_code == 200
        assert response.json() == []
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_contract_activity_accepts_limit_lower_boundary(self):
        service = AsyncMock()
        service.list_by_organization.return_value = []
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=0")

        assert response.status_code == 200
        assert response.json() == []
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=0, offset=0)

    @pytest.mark.asyncio
    async def test_contract_activity_accepts_limit_upper_boundary(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=100")

        assert response.status_code == 200
        assert response.json() == [_expected_activity_payload()]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_invalid_contract_activity_limit_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=101")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_numeric_contract_activity_limit_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?limit=abc")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_contract_activity_offset_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?offset=-1")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_numeric_contract_activity_offset_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts?offset=abc")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_contract_activity(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/contracts")

        assert response.status_code == 403
        assert response.json()["message"] == "Solo los administradores pueden consultar la auditoria de contratos"
        service.list_by_organization.assert_not_awaited()
