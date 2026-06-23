"""Paywall expectations for premium chatbot access."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.billing.api.dependencies import get_paypal_subscription_service
from contractai_backend.modules.chatbot.api.dependencies import get_chatbot_service
from contractai_backend.modules.chatbot.api.routers.chat_router import router
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import get_current_user


def _make_user() -> UserTable:
    return UserTable(
        id=1,
        organization_id=10,
        email="worker@example.com",
        full_name="Worker User",
        role=UserRole.WORKER,
        is_active=True,
    )


def _make_app(chatbot_service, subscription_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/chatbot")
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    app.dependency_overrides[get_chatbot_service] = lambda: chatbot_service
    app.dependency_overrides[get_paypal_subscription_service] = lambda: subscription_service
    return app


class TestChatbotPaywall:
    @pytest.mark.asyncio
    async def test_chatbot_blocks_inactive_subscription_before_processing_message(self):
        chatbot_service = AsyncMock()
        chatbot_service.process_user_message.return_value = ("respuesta", 1, None)
        subscription_service = AsyncMock()
        subscription_service.check_subscription_active.return_value = False
        app = _make_app(chatbot_service=chatbot_service, subscription_service=subscription_service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/chatbot/", json={"message": "Analiza mis contratos", "thread_id": None})

        assert response.status_code == 403
        subscription_service.check_subscription_active.assert_awaited_once_with(10)
        chatbot_service.process_user_message.assert_not_awaited()
