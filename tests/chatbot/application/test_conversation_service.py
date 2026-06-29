"""Tests unitarios para ConversationService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pactus_backend.modules.chatbot.application.services.conversation_service import ConversationService
from pactus_backend.modules.chatbot.domain.entities import ConversationTable


def _make_conv(id: int = 1) -> ConversationTable:
    return ConversationTable(id=id, organization_id=1, user_id=1, title="Test", content=[])


def _make_service(repo=None) -> ConversationService:
    return ConversationService(repository=repo or AsyncMock())


class TestCreateConversation:
    @pytest.mark.asyncio
    async def test_creates_and_returns_conversation(self):
        conv = _make_conv()
        repo = AsyncMock()
        repo.save.return_value = conv

        service = _make_service(repo)
        result = await service.create_conversation(organization_id=1, user_id=1, title="Test")

        assert result.title == "Test"
        repo.save.assert_called_once()


class TestGetConversation:
    @pytest.mark.asyncio
    async def test_returns_conversation_read(self):
        conv = _make_conv()
        repo = AsyncMock()
        repo.get_visible_by_id.return_value = conv

        service = _make_service(repo)
        result = await service.get_conversation(conversation_id=1, organization_id=1, user_id=1)

        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo = AsyncMock()
        repo.get_visible_by_id.return_value = None

        service = _make_service(repo)
        result = await service.get_conversation(conversation_id=99, organization_id=1, user_id=1)

        assert result is None


class TestListUserConversations:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        convs = [_make_conv(1), _make_conv(2)]
        repo = AsyncMock()
        repo.get_by_user.return_value = convs

        service = _make_service(repo)
        result = await service.list_user_conversations(organization_id=1, user_id=1)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        repo = AsyncMock()
        repo.get_by_user.return_value = []

        service = _make_service(repo)
        result = await service.list_user_conversations(organization_id=1, user_id=99)

        assert result == []


class TestAppendMessages:
    @pytest.mark.asyncio
    async def test_returns_updated_conversation(self):
        conv = _make_conv()
        repo = AsyncMock()
        repo.update_messages.return_value = conv

        service = _make_service(repo)
        result = await service.append_messages(
            conversation_id=1,
            organization_id=1,
            user_id=1,
            new_messages=[{"role": "user", "content": "hi"}],
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo = AsyncMock()
        repo.update_messages.return_value = None

        service = _make_service(repo)
        result = await service.append_messages(conversation_id=99, organization_id=1, user_id=1, new_messages=[])

        assert result is None
