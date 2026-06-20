"""Tests for template activity audit router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.audit.api.dependencies import get_template_activity_service
from contractai_backend.modules.audit.api.routers.template_activity_router import router
from contractai_backend.modules.audit.domain.entities import TemplateActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditTemplateAction
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/audit")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_template_activity_service] = lambda: service
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
    action: AuditTemplateAction = AuditTemplateAction.CREATED,
    template_id: int | None = 42,
    template_format_id: int | None = 3,
    template_name: str | None = "Standard Services Template",
    document_type: str | None = "COMPANY",
    previous_state: str | None = None,
    state: str | None = "DRAFT",
    created_at: datetime = datetime(2026, 6, 12, tzinfo=UTC),
) -> TemplateActivityTable:
    return TemplateActivityTable(
        id=id,
        organization_id=10,
        actor_user_id=1,
        actor_name="Admin User",
        actor_role="ADMIN",
        action=action,
        template_id=template_id,
        template_format_id=template_format_id,
        template_name=template_name,
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
        "action": "CREATED",
        "template_id": 42,
        "template_format_id": 3,
        "template_name": "Standard Services Template",
        "document_type": "COMPANY",
        "previous_state": None,
        "state": "DRAFT",
        "created_at": "2026-06-12T00:00:00Z",
    }


class TestTemplateActivityRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_own_organization_template_activity(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=25&offset=5")

        assert response.status_code == 200
        assert response.json() == [_expected_activity_payload()]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=25, offset=5)

    @pytest.mark.asyncio
    async def test_admin_lists_multiple_template_activity_states_without_mixing_fields(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [
            _make_activity(id=1, template_name="Draft Template", state="DRAFT"),
            _make_activity(
                id=2,
                action=AuditTemplateAction.ARCHIVED,
                template_id=77,
                template_format_id=9,
                template_name="Archived Labor Template",
                document_type="LABOR",
                previous_state="PUBLISHED",
                state="ARCHIVED",
                created_at=datetime(2026, 6, 13, tzinfo=UTC),
            ),
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=100&offset=0")

        assert response.status_code == 200
        assert response.json() == [
            {
                **_expected_activity_payload(),
                "template_name": "Draft Template",
            },
            {
                **_expected_activity_payload(),
                "id": 2,
                "action": "ARCHIVED",
                "template_id": 77,
                "template_format_id": 9,
                "template_name": "Archived Labor Template",
                "document_type": "LABOR",
                "previous_state": "PUBLISHED",
                "state": "ARCHIVED",
                "created_at": "2026-06-13T00:00:00Z",
            },
        ]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_admin_lists_template_activity_with_nullable_panel_fields(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [
            _make_activity(
                action=AuditTemplateAction.DELETED,
                template_id=None,
                template_format_id=None,
                template_name=None,
                document_type=None,
                previous_state="ARCHIVED",
                state=None,
            )
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates")

        assert response.status_code == 200
        assert response.json() == [
            {
                **_expected_activity_payload(),
                "action": "DELETED",
                "template_id": None,
                "template_format_id": None,
                "template_name": None,
                "document_type": None,
                "previous_state": "ARCHIVED",
                "state": None,
            }
        ]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_admin_lists_empty_template_activity_with_default_pagination(self):
        service = AsyncMock()
        service.list_by_organization.return_value = []
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates")

        assert response.status_code == 200
        assert response.json() == []
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_template_activity_accepts_limit_lower_boundary(self):
        service = AsyncMock()
        service.list_by_organization.return_value = []
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=0")

        assert response.status_code == 200
        assert response.json() == []
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=0, offset=0)

    @pytest.mark.asyncio
    async def test_template_activity_accepts_limit_upper_boundary(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=100")

        assert response.status_code == 200
        assert response.json() == [_expected_activity_payload()]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=100, offset=0)

    @pytest.mark.asyncio
    async def test_invalid_template_activity_limit_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=101")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_numeric_template_activity_limit_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?limit=abc")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_template_activity_offset_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?offset=-1")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_numeric_template_activity_offset_returns_422_without_calling_service(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates?offset=abc")

        assert response.status_code == 422
        service.list_by_organization.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_template_activity(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/templates")

        assert response.status_code == 403
        assert response.json()["message"] == "Solo los administradores pueden consultar la auditoria de plantillas"
        service.list_by_organization.assert_not_awaited()
