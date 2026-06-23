"""Tests for AI token quota enforcement."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.audit.application.services import AITokenTrackingService
from contractai_backend.modules.audit.domain.exceptions import LLMQuotaExceededError
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user() -> UserTable:
    return UserTable(
        id=5,
        organization_id=10,
        email="worker@example.com",
        full_name="Worker User",
        role=UserRole.WORKER,
        is_active=True,
    )


class TestAITokenTrackingServiceRateLimit:
    @pytest.mark.asyncio
    async def test_check_rate_limit_blocks_user_at_daily_token_limit(self, monkeypatch):
        repository = AsyncMock()
        repository.get_daily_token_usage_by_user.return_value = 100
        monkeypatch.setattr("contractai_backend.modules.audit.application.services.ai_token_tracking_service.settings.MAX_DAILY_TOKENS_PER_USER", 100)
        service = AITokenTrackingService(repository=repository)

        with pytest.raises(LLMQuotaExceededError):
            await service.check_rate_limit(actor=_make_user())

        repository.get_daily_token_usage_by_user.assert_awaited_once_with(actor_user_id=5)
