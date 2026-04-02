"""Tests unitarios para ConversationRepository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from contractai_backend.modules.chatbot.domain.entities import ConversationTable
from contractai_backend.modules.chatbot.infrastructure.conversation_repo import ConversationRepository


def _make_conv(id: int = 1) -> ConversationTable:
    return ConversationTable(id=id, organization_id=1, user_id=1, title="Test", content=[])


def _make_repo() -> tuple[ConversationRepository, AsyncMock]:
    session = AsyncMock()
    repo = ConversationRepository(session=session)
    return repo, session


class TestUpdateMessages:
    @pytest.mark.asyncio
    async def test_returns_none_when_conversation_not_found(self):
        repo, session = _make_repo()
        # get_by_id returns None
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        result = await repo.update_messages(99, [{"role": "user", "content": "hi"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_appends_messages_and_commits(self):
        repo, session = _make_repo()
        conv = _make_conv()

        result_mock = MagicMock()
        result_mock.first.return_value = conv
        session.exec.return_value = result_mock
        session.refresh = AsyncMock()

        result = await repo.update_messages(1, [{"role": "user", "content": "hi"}])

        session.add.assert_called_once_with(instance=conv)
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_updated_at_is_refreshed(self):
        repo, session = _make_repo()
        conv = _make_conv()
        old_time = conv.updated_at

        result_mock = MagicMock()
        result_mock.first.return_value = conv
        session.exec.return_value = result_mock
        session.refresh = AsyncMock()

        await repo.update_messages(1, [{"role": "bot", "content": "resp"}])

        assert conv.updated_at >= old_time


class TestGetByUser:
    @pytest.mark.asyncio
    async def test_returns_conversations_for_user(self):
        repo, session = _make_repo()
        convs = [_make_conv(1), _make_conv(2)]

        result_mock = MagicMock()
        result_mock.all.return_value = convs
        session.exec.return_value = result_mock

        result = await repo.get_by_user(user_id=1)
        assert result == convs

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_conversations(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        result = await repo.get_by_user(user_id=99)
        assert result == []
