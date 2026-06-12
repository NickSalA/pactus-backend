"""Tests for ContractActivityService."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.audit.application.services import ContractActivityService
from contractai_backend.modules.audit.domain.value_objs import AuditContractAction
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


class TestContractActivityService:
    @pytest.mark.asyncio
    async def test_record_created_builds_activity(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)
        actor = _make_user(id=1)

        result = await service.record(
            action=AuditContractAction.CREATED,
            actor=actor,
            document_id=42,
            document_name="contract.pdf",
            document_type="COMPANY",
            state="DRAFT",
        )

        assert result.action == AuditContractAction.CREATED
        assert result.organization_id == actor.organization_id
        assert result.actor_user_id == actor.id
        assert result.actor_name == actor.full_name
        assert result.document_id == 42
        assert result.document_name == "contract.pdf"
        assert result.document_type == "COMPANY"
        assert result.state == "DRAFT"
        assert result.previous_state is None
        repo.record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_deleted_snapshots_metadata(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)
        actor = _make_user(id=1)

        result = await service.record(
            action=AuditContractAction.DELETED,
            actor=actor,
            document_id=42,
            document_name="deleted_contract.pdf",
            document_type="LABOR",
            previous_state="ACTIVE",
            state=None,
        )

        assert result.action == AuditContractAction.DELETED
        assert result.document_name == "deleted_contract.pdf"
        assert result.document_type == "LABOR"
        assert result.previous_state == "ACTIVE"
        assert result.state is None

    @pytest.mark.asyncio
    async def test_record_uses_email_fallback_when_no_full_name(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)
        actor = _make_user(id=2, full_name=None, email="worker@test.com")

        result = await service.record(
            action=AuditContractAction.UPDATED,
            actor=actor,
            document_id=1,
        )

        assert result.actor_name == "worker@test.com"
