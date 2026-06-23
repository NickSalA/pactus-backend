"""Tests for user activity audit router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.audit.api.dependencies import get_chatbot_activity_service, get_user_activity_service
from contractai_backend.modules.audit.api.routers.chatbot_activity_router import router as chatbot_router
from contractai_backend.modules.audit.api.routers.user_activity_router import router
from contractai_backend.modules.audit.domain.entities import ChatbotActivityTable, UserActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction, AuditUserAction
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/audit")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_user_activity_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=10,
        email="admin@example.com",
        full_name="Admin User",
        role=role,
        is_active=True,
    )
    return app


def _make_chatbot_app(service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(chatbot_router, prefix="/audit")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_chatbot_activity_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=10,
        email="admin@example.com",
        full_name="Admin User",
        role=role,
        is_active=True,
    )
    return app


def _make_activity() -> UserActivityTable:
    return UserActivityTable(
        id=1,
        organization_id=10,
        actor_user_id=1,
        actor_name="Admin User",
        actor_role="ADMIN",
        action=AuditUserAction.CREATED,
        target_user_id=2,
        target_user_email="worker@example.com",
        target_user_name="Worker",
        previous_role=None,
        role="WORKER",
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
    )


def _make_chatbot_activity() -> ChatbotActivityTable:
    return ChatbotActivityTable(
        id=1,
        organization_id=10,
        actor_user_id=2,
        actor_name="Worker",
        actor_role="WORKER",
        action=AuditChatbotAction.RESPONSE_GENERATED,
        conversation_id=5,
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
    )


class TestUserActivityRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_own_organization_activity(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [_make_activity()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/users?limit=25&offset=5")

        assert response.status_code == 200
        assert response.json()[0]["action"] == "CREATED"
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=25, offset=5)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_activity(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/users")

        assert response.status_code == 403
        assert response.json()["type"] == "ForbiddenError"
        service.list_by_organization.assert_not_awaited()


class TestChatbotActivityRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_own_organization_chatbot_activity(self):
        service = AsyncMock()
        service.list_by_organization.return_value = [(_make_chatbot_activity(), "Contrato de servicios")]
        app = _make_chatbot_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/chatbot?limit=10&offset=2")

        assert response.status_code == 200
        assert response.json()[0]["action"] == "RESPONSE_GENERATED"
        assert response.json()[0]["conversation_title"] == "Contrato de servicios"
        assert "conversation_id" not in response.json()[0]
        service.list_by_organization.assert_awaited_once_with(organization_id=10, limit=10, offset=2)

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_chatbot_activity(self):
        service = AsyncMock()
        app = _make_chatbot_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/chatbot")

        assert response.status_code == 403
        assert response.json()["type"] == "ForbiddenError"
        service.list_by_organization.assert_not_awaited()
