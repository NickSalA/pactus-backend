"""Service for read-only operations on documents, such as listing and fetching."""

from collections.abc import Sequence

from ....users.domain.value_objs import UserRole
from ...domain.access_policy import can_read_document_type
from ...domain.value_objs import DocumentType
from ..dto import DocumentResponse
from ..repositories import DocumentQueryRepository
from .document_response_assembler import DocumentResponseAssembler


class DocumentQueryService:
    def __init__(self, sql_repo: DocumentQueryRepository):
        """Stores the query repo for read-only operations."""
        self.sql_repo = sql_repo
        self.response_assembler = DocumentResponseAssembler(sql_repo=sql_repo)

    @staticmethod
    def _can_read_document_kind(document_kind: str | None, user_role: UserRole | None) -> bool:
        if document_kind is None:
            return True
        return can_read_document_type(user_role=user_role, document_type=DocumentType(document_kind))

    async def get_documents(
        self,
        organization_id: int,
        user_role: UserRole | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[DocumentResponse]:
        """Lists documents for the given organization with optional pagination."""
        await self.sql_repo.sync_contract_states(organization_id=organization_id)
        all_documents = await self.sql_repo.get_all(filters={"organization_id": organization_id}, limit=limit, offset=offset)
        all_document_ids = [document.id for document in all_documents if document.id is not None]
        document_kinds = await self.sql_repo.get_contract_kinds_by_document_ids(document_ids=all_document_ids)
        documents = [document for document in all_documents if self._can_read_document_kind(document_kinds.get(document.id), user_role=user_role)]
        document_ids = [document.id for document in documents if document.id is not None]
        service_items_by_document = {}

        if document_ids:
            service_items_by_document = await self.sql_repo.get_document_services_by_document_ids(document_ids=document_ids)

        return await self.response_assembler.build_many(
            documents=documents,
            service_items_by_document=service_items_by_document,
        )

    async def get_document(self, id: int, organization_id: int, user_role: UserRole | None = None) -> DocumentResponse | None:
        """Returns one document if it belongs to the org."""
        await self.sql_repo.sync_contract_states(organization_id=organization_id)
        document = await self.sql_repo.get_by_id(id)
        if document is None or document.organization_id != organization_id:
            return None
        document_kind = None
        if document.id is not None:
            document_kind = (await self.sql_repo.get_contract_kinds_by_document_ids(document_ids=[document.id])).get(document.id)
        if not self._can_read_document_kind(document_kind, user_role=user_role):
            return None

        return await self.response_assembler.build(document=document)
