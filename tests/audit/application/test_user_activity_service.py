"""Tests for UserActivityService."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.audit.application.services import ChatbotActivityService, UserActivityService
from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction, AuditUserAction
from contractai_backend.modules.chatbot.application.dto import TokenCostResult
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user(**kwargs) -> UserTable:
    defaults = {
        "id": 1,
        "organization_id": 10,
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": UserRole.ADMIN,
        "is_active": True,
    }
    defaults.update(kwargs)
    return UserTable(**defaults)


class TestUserActivityService:
    @pytest.mark.asyncio
    async def test_record_created_builds_activity_from_actor_and_target(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = UserActivityService(repository=repo)
        actor = _make_user(id=1, email="admin@example.com", role=UserRole.ADMIN)
        target = _make_user(id=2, email="worker@example.com", full_name="Worker", role=UserRole.WORKER)

        result = await service.record_created(actor=actor, target=target)

        assert result.action == AuditUserAction.CREATED
        assert result.organization_id == actor.organization_id
        assert result.actor_user_id == actor.id
        assert result.actor_role == UserRole.ADMIN
        assert result.target_user_id == target.id
        assert result.target_user_email == target.email
        assert result.role == UserRole.WORKER
        assert result.previous_role is None
        repo.record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_updated_includes_previous_role(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = UserActivityService(repository=repo)
        actor = _make_user(id=1, role=UserRole.ADMIN)
        target = _make_user(id=2, email="hr@example.com", role=UserRole.HR)

        result = await service.record_updated(actor=actor, target=target, previous_role=UserRole.WORKER)

        assert result.action == AuditUserAction.UPDATED
        assert result.previous_role == UserRole.WORKER
        assert result.role == UserRole.HR


class TestChatbotActivityService:
    @pytest.mark.asyncio
    async def test_record_conversation_started_builds_activity(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ChatbotActivityService(repository=repo)
        actor = _make_user(id=3, email="worker@example.com", role=UserRole.WORKER)

        result = await service.record_conversation_started(actor=actor, conversation_id=99)

        assert result.action == AuditChatbotAction.CONVERSATION_STARTED
        assert result.organization_id == actor.organization_id
        assert result.actor_user_id == actor.id
        assert result.actor_role == UserRole.WORKER
        assert result.conversation_id == 99
        assert result.input_tokens is None
        repo.record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_response_generated_includes_costs(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ChatbotActivityService(repository=repo)
        actor = _make_user(id=3, role=UserRole.HR)
        cost = TokenCostResult(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            input_cost_usd=0.0001,
            output_cost_usd=0.0002,
            total_cost_usd=0.0003,
            model_used="gemini-test",
        )

        result = await service.record_response_generated(actor=actor, conversation_id=10, cost=cost)

        assert result.action == AuditChatbotAction.RESPONSE_GENERATED
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert str(result.total_cost_usd) == "0.0003"
        assert result.model_used == "gemini-test"
