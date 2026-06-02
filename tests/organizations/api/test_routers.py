"""Tests for organization routers with mocked dependencies."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.organizations.api.dependencies import get_organization_service
from contractai_backend.modules.organizations.api.routers.organizations_router import router
from contractai_backend.modules.organizations.application.dto import OrganizationResponse
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.config import settings
from contractai_backend.shared.api.dependencies.security import get_current_user


def _make_app(mock_service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/organizations")
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=1,
        email="admin@example.com",
        full_name="Admin User",
        role=role,
        is_active=True,
    )
    app.dependency_overrides[get_organization_service] = lambda: mock_service
    return app


def _organization_response() -> OrganizationResponse:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    return OrganizationResponse(id=1, name="Org 1", is_active=True, created_at=now, updated_at=now)


class TestOrganizationRouter:
    @pytest.mark.asyncio
    async def test_list_organizations_accepts_valid_pagination(self):
        service = AsyncMock()
        service.list_organizations.return_value = [_organization_response()]
        app = _make_app(service, role=UserRole.SUPERADMIN)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/organizations?limit=25&offset=10")

        assert response.status_code == 200
        assert response.json()[0]["id"] == 1
        service.list_organizations.assert_awaited_once_with(is_active=None, name=None, ruc=None, limit=25, offset=10)

    @pytest.mark.asyncio
    async def test_list_organizations_rejects_negative_offset(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/organizations?offset=-1")

        assert response.status_code == 422
        service.list_organizations.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_list_organizations_rejects_too_large_limit(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/organizations?limit={settings.MAX_ORGANIZATIONS_LIMIT + 1}")

        assert response.status_code == 422
        service.list_organizations.assert_not_awaited()
