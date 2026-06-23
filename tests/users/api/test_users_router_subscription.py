"""Tests for subscription status exposed by the users API."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.billing.api.dependencies import get_paypal_subscription_service
from contractai_backend.modules.users.api.routers.users_router import router
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import get_current_user


def _make_user(organization_id: int = 10) -> UserTable:
    return UserTable(
        id=1,
        organization_id=organization_id,
        email="admin@example.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )


def _make_app(current_user: UserTable, subscription_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/user")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_paypal_subscription_service] = lambda: subscription_service
    return app


class TestGetMeSubscriptionStatus:
    @pytest.mark.asyncio
    async def test_get_me_returns_subscription_active_true_when_paypal_subscription_is_active(self):
        service = AsyncMock()
        service.check_subscription_active.return_value = True
        app = _make_app(current_user=_make_user(organization_id=10), subscription_service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/user/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["organization_id"] == 10
        assert data["subscription_active"] is True
        service.check_subscription_active.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_get_me_returns_subscription_active_false_when_paypal_subscription_is_inactive(self):
        service = AsyncMock()
        service.check_subscription_active.return_value = False
        app = _make_app(current_user=_make_user(organization_id=10), subscription_service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/user/me")

        assert response.status_code == 200
        assert response.json()["subscription_active"] is False
        service.check_subscription_active.assert_awaited_once_with(10)

    @pytest.mark.asyncio
    async def test_get_me_checks_subscription_for_authenticated_users_organization(self):
        service = AsyncMock()
        service.check_subscription_active.return_value = True
        app = _make_app(current_user=_make_user(organization_id=77), subscription_service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/user/me")

        assert response.status_code == 200
        assert response.json()["organization_id"] == 77
        service.check_subscription_active.assert_awaited_once_with(77)
