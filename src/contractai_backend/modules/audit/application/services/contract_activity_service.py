"""Application service for contract activity auditing."""

from collections.abc import Sequence
from typing import Any

from contractai_backend.modules.audit.application.repositories import ContractActivityRepository
from contractai_backend.modules.audit.domain.entities import ContractActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditContractAction


class ContractActivityService:
    """Records and lists contract-management audit activity."""

    def __init__(self, repository: ContractActivityRepository) -> None:
        self.repository = repository

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ContractActivityTable]:
        return await self.repository.list_by_organization(organization_id=organization_id, limit=limit, offset=offset)

    async def record(
        self,
        *,
        action: AuditContractAction,
        actor: Any,
        document_id: int | None = None,
        company_contract_id: int | None = None,
        labor_contract_id: int | None = None,
        document_name: str | None = None,
        document_type: str | None = None,
        previous_state: str | None = None,
        state: str | None = None,
    ) -> ContractActivityTable:
        """Records a contract audit event."""
        actor_name = getattr(actor, "full_name", None) or getattr(actor, "email", None)
        actor_role = str(getattr(actor, "role", ""))
        activity = ContractActivityTable(
            organization_id=getattr(actor, "organization_id", 0),
            actor_user_id=getattr(actor, "id", 0),
            actor_name=actor_name,
            actor_role=actor_role,
            action=action,
            document_id=document_id,
            company_contract_id=company_contract_id,
            labor_contract_id=labor_contract_id,
            document_name=document_name,
            document_type=document_type,
            previous_state=previous_state,
            state=state,
        )
        return await self.repository.record(activity)
