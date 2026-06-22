"""Tests for ContractActivityService."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.audit.application.services import ContractActivityService
from contractai_backend.modules.audit.domain.value_objs import AuditContractAction


class TestContractActivityService:
    @pytest.mark.asyncio
    async def test_record_builds_activity_from_defensive_getattr(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)

        from types import SimpleNamespace
        actor = SimpleNamespace(
            id=1,
            organization_id=10,
            email="admin@example.com",
            full_name="Admin User",
            role="ADMIN",
        )

        result = await service.record(
            action=AuditContractAction.MANUAL_UPLOAD,
            actor=actor,
            document_id=100,
            document_name="contrato.pdf",
            document_type="COMPANY",
            state="ACTIVE",
        )

        assert result.action == AuditContractAction.CREATED
        assert result.organization_id == 10
        assert result.actor_user_id == 1
        assert result.actor_name == "Admin User"
        assert result.document_id == 100
        assert result.document_name == "contrato.pdf"
        assert result.document_type == "COMPANY"
        assert result.state == "ACTIVE"
        repo.record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_includes_previous_state_on_update(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)

        from types import SimpleNamespace
        actor = SimpleNamespace(
            id=1,
            organization_id=10,
            email="admin@example.com",
            full_name="Admin User",
            role="ADMIN",
        )

        result = await service.record(
            action=AuditContractAction.UPDATED,
            actor=actor,
            document_id=100,
            document_name="contrato.pdf",
            document_type="COMPANY",
            previous_state="DRAFT",
            state="ACTIVE",
        )

        assert result.action == AuditContractAction.UPDATED
        assert result.previous_state == "DRAFT"
        assert result.state == "ACTIVE"
        repo.record.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_fallback_with_empty_actor(self):
        repo = AsyncMock()
        repo.record.side_effect = lambda activity: activity
        service = ContractActivityService(repository=repo)

        from types import SimpleNamespace
        actor = SimpleNamespace()

        result = await service.record(
            action=AuditContractAction.DELETED,
            actor=actor,
            document_name="deleted.pdf",
            document_type="LABOR",
            state="TERMINATED",
        )

        assert result.action == AuditContractAction.DELETED
        assert result.actor_name is None
        assert result.actor_role == ""
        repo.record.assert_awaited_once()
