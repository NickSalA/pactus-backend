"""Tests unitarios para ChatbotService."""

from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from contractai_backend.modules.chatbot.application.repositories.base_llm import LLMResult
from contractai_backend.modules.chatbot.application.services.chatbot_service import ChatbotService
from contractai_backend.modules.chatbot.domain.entities import ConversationTable
from contractai_backend.modules.chatbot.domain.exceptions import ConversationNotFoundError
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user(id: int = 1, org_id: int = 1):
    user = MagicMock()
    user.id = id
    user.organization_id = org_id
    user.role = UserRole.WORKER
    user.full_name = "Test User"
    return user


def _make_conv(id: int = 5) -> ConversationTable:
    return ConversationTable(id=id, organization_id=1, user_id=1, title="Test", content=[])


def _make_llm_result(response: str = "Respuesta del bot", thread_id: int = 5) -> LLMResult:
    return LLMResult(response=response, thread_id=thread_id, input_tokens=100, output_tokens=50, total_tokens=150, model_used="gemini-2.5-flash")


def _make_service(llm=None, conv_service=None) -> ChatbotService:
    return ChatbotService(llm_provider=llm or AsyncMock(), conv_service=conv_service or AsyncMock())


class TestProcessUserMessage:
    @pytest.mark.asyncio
    async def test_creates_new_conversation_when_no_thread(self):
        conv = _make_conv(id=5)
        conv_service = AsyncMock()
        conv_service.create_conversation.return_value = conv
        conv_service.append_messages.return_value = conv

        llm = AsyncMock()
        llm.invoke.return_value = _make_llm_result(response="Respuesta del bot", thread_id=5)

        service = _make_service(llm=llm, conv_service=conv_service)
        response, thread_id = await service.process_user_message("Hola", thread_id=None, current_user=_make_user())

        assert response == "Respuesta del bot"
        assert thread_id == 5
        conv_service.create_conversation.assert_called_once()
        conv_service.append_messages.assert_awaited_once()
        llm.invoke.assert_awaited_once_with(message="Hola", thread_id=5, user_context=ANY)

    @pytest.mark.asyncio
    async def test_uses_existing_thread_id(self):
        conv = _make_conv(id=10)
        conv_service = AsyncMock()
        conv_service.append_messages.side_effect = [conv, conv]

        llm = AsyncMock()
        llm.invoke.return_value = _make_llm_result(response="Respuesta", thread_id=10)

        service = _make_service(llm=llm, conv_service=conv_service)
        response, thread_id = await service.process_user_message("Hola", thread_id=10, current_user=_make_user())

        assert thread_id == 10
        conv_service.create_conversation.assert_not_called()
        assert conv_service.append_messages.await_count == 2

    @pytest.mark.asyncio
    async def test_title_truncated_at_30_chars(self):
        long_message = "A" * 50
        conv = _make_conv()
        conv_service = AsyncMock()
        conv_service.create_conversation.return_value = conv
        conv_service.append_messages.return_value = conv

        llm = AsyncMock()
        llm.invoke.return_value = _make_llm_result(response="ok", thread_id=conv.id)

        service = _make_service(llm=llm, conv_service=conv_service)
        await service.process_user_message(long_message, thread_id=None, current_user=_make_user())

        call_kwargs = conv_service.create_conversation.call_args.kwargs
        assert len(call_kwargs["title"]) <= 33  # 30 chars + "..."

    @pytest.mark.asyncio
    async def test_raises_when_existing_thread_is_not_owned_or_not_found(self):
        conv_service = AsyncMock()
        conv_service.append_messages.return_value = None

        llm = AsyncMock()

        service = _make_service(llm=llm, conv_service=conv_service)
        with pytest.raises(ConversationNotFoundError):
            await service.process_user_message("Hola", thread_id=10, current_user=_make_user())

        llm.invoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_when_bot_append_returns_none(self):
        conv = _make_conv()
        conv_service = AsyncMock()
        conv_service.create_conversation.return_value = conv
        conv_service.append_messages.return_value = None

        llm = AsyncMock()
        llm.invoke.return_value = _make_llm_result(response="ok", thread_id=conv.id)

        service = _make_service(llm=llm, conv_service=conv_service)
        with pytest.raises(ConversationNotFoundError):
            await service.process_user_message("Hola", thread_id=None, current_user=_make_user())
