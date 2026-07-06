"""Tests for conversation router access rules."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pactus_backend.core.exceptions.base import AppError
from pactus_backend.modules.chatbot.api.dependencies import get_conversation_service
from pactus_backend.modules.chatbot.api.routers.conversation_router import router
from pactus_backend.modules.chatbot.domain.entities import ConversationTable
from pactus_backend.shared.api.dependencies.security import get_current_user
from pactus_backend.shared.api.error_handlers import app_error_handler


def _make_app(current_user, service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/conversations")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_conversation_service] = lambda: service
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    return app


def _make_conv(id: int = 1) -> ConversationTable:
    return ConversationTable(id=id, organization_id=1, user_id=1, title="Test", content=[])


class TestListConversations:
    @pytest.mark.asyncio
    async def test_forbids_listing_another_users_conversations(self):
        service = AsyncMock()
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/conversations/user/2")

        assert response.status_code == 403
        service.list_user_conversations.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lists_only_authenticated_users_conversations(self):
        service = AsyncMock()
        service.list_user_conversations.return_value = [_make_conv(1)]
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/conversations/user/1")

        assert response.status_code == 200
        service.list_user_conversations.assert_awaited_once_with(organization_id=1, user_id=1)


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_returns_404_when_conversation_is_not_visible(self):
        service = AsyncMock()
        service.get_conversation.return_value = None
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/conversations/99")

        assert response.status_code == 404
        service.get_conversation.assert_awaited_once_with(conversation_id=99, organization_id=1, user_id=1)

    @pytest.mark.asyncio
    async def test_returns_conversation_data(self):
        conv = _make_conv(id=1)
        service = AsyncMock()
        service.get_conversation.return_value = conv
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/conversations/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["title"] == "Test"
        service.get_conversation.assert_awaited_once_with(conversation_id=1, organization_id=1, user_id=1)


class TestUpdateConversation:
    @pytest.mark.asyncio
    async def test_updates_conversation_title(self):
        conv = _make_conv(id=1)
        service = AsyncMock()
        service.update_conversation_title.return_value = conv
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/conversations/1", json={"title": "Nuevo titulo"})

        assert response.status_code == 200
        assert response.json()["title"] == "Test"
        service.update_conversation_title.assert_awaited_once_with(
            conversation_id=1,
            organization_id=1,
            user_id=1,
            title="Nuevo titulo",
        )

    @pytest.mark.asyncio
    async def test_returns_404_when_updating_nonexistent_conversation(self):
        service = AsyncMock()
        service.update_conversation_title.return_value = None
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/conversations/99", json={"title": "Nuevo titulo"})

        assert response.status_code == 404


class TestDeleteConversation:
    @pytest.mark.asyncio
    async def test_deletes_conversation(self):
        service = AsyncMock()
        service.delete_conversation.return_value = True
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/conversations/1")

        assert response.status_code == 204
        assert response.content == b""
        service.delete_conversation.assert_awaited_once_with(conversation_id=1, organization_id=1, user_id=1)

    @pytest.mark.asyncio
    async def test_returns_404_when_deleting_nonexistent_conversation(self):
        service = AsyncMock()
        service.delete_conversation.return_value = False
        current_user = SimpleNamespace(id=1, organization_id=1)
        app = _make_app(current_user=current_user, service=service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/conversations/99")

        assert response.status_code == 404
