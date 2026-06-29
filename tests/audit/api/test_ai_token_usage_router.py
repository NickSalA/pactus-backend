"""Tests for AI token usage audit router."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pactus_backend.core.exceptions.base import AppError
from pactus_backend.modules.audit.api.dependencies import get_ai_token_tracking_service
from pactus_backend.modules.audit.api.routers.ai_token_usage_router import router
from pactus_backend.modules.audit.domain.entities import AITokenUsageTable
from pactus_backend.modules.audit.domain.value_objs import AITokenSource
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole
from pactus_backend.shared.api.dependencies.security import get_current_user
from pactus_backend.shared.api.error_handlers import app_error_handler


def _make_app(service, role: UserRole = UserRole.ADMIN) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/audit")
    app.add_exception_handler(AppError, app_error_handler)
    app.dependency_overrides[get_ai_token_tracking_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=10,
        email="admin@example.com",
        full_name="Admin User",
        role=role,
        is_active=True,
    )
    return app


def _make_token_usage() -> AITokenUsageTable:
    return AITokenUsageTable(
        id=1,
        organization_id=10,
        actor_user_id=1,
        source=AITokenSource.CHATBOT,
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        input_cost_usd=Decimal("0.0015"),
        output_cost_usd=Decimal("0.0030"),
        total_cost_usd=Decimal("0.0045"),
        model_used="gemini-1.5-pro",
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
    )


class TestAITokenUsageRouter:
    @pytest.mark.asyncio
    async def test_admin_lists_token_usage_with_optional_filters(self):
        service = AsyncMock()
        service.list_usage.return_value = [_make_token_usage()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/audit/ai-usage"
                "?limit=10"
                "&offset=2"
                "&user_id=1"
                "&source=CHATBOT"
                "&start_date=2026-06-01T00:00:00Z"
                "&end_date=2026-06-30T23:59:59Z"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["source"] == "CHATBOT"
        assert data[0]["total_tokens"] == 300
        assert data[0]["total_cost_usd"] == 0.0045
        assert data[0]["model_used"] == "gemini-1.5-pro"
        service.list_usage.assert_awaited_once_with(
            organization_id=10,
            limit=10,
            offset=2,
            actor_user_id=1,
            source=AITokenSource.CHATBOT,
            start_date=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
        )

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_token_usage(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/ai-usage")

        assert response.status_code == 403
        assert response.json()["type"] == "ForbiddenError"
        service.list_usage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_gets_token_usage_summary(self):
        service = AsyncMock()
        service.get_summary.return_value = {
            "total_tokens": 1000,
            "total_cost_usd": 0.015,
            "input_tokens": 400,
            "output_tokens": 600,
        }
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/audit/ai-usage/summary"
                "?user_id=1"
                "&start_date=2026-06-01T00:00:00Z"
                "&end_date=2026-06-30T23:59:59Z"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tokens"] == 1000
        assert data["total_cost_usd"] == 0.015
        assert data["input_tokens"] == 400
        assert data["output_tokens"] == 600
        service.get_summary.assert_awaited_once_with(
            organization_id=10,
            actor_user_id=1,
            start_date=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
            end_date=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
        )

    @pytest.mark.asyncio
    async def test_non_admin_cannot_get_summary(self):
        service = AsyncMock()
        app = _make_app(service, role=UserRole.WORKER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/audit/ai-usage/summary")

        assert response.status_code == 403
        assert response.json()["type"] == "ForbiddenError"
        service.get_summary.assert_not_awaited()
