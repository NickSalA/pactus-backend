"""Service for read-only operations on documents, such as listing and fetching."""

from collections.abc import Sequence

from ...api.schemas import DocumentResponse
from ...domain import DocumentTable
from ...domain.access_policy import can_read_document_type, filter_readable_documents
from ...domain.value_objs import DocumentType
from ..repositories import DocumentQueryRepository
from .document_response_assembler import DocumentResponseAssembler
from ....users.domain.value_objs import UserRole


class DocumentQueryService:
    def __init__(self, sql_repo: DocumentQueryRepository):
        """Stores the query repo for read-only operations."""
        self.sql_repo = sql_repo
        self.response_assembler = DocumentResponseAssembler(sql_repo=sql_repo)

    async def get_documents(self, organization_id: int, user_role: UserRole | None = None) -> Sequence[DocumentResponse]:
        """Lists documents for the given organization."""
        await self.sql_repo.sync_contract_states(organization_id=organization_id)
        documents: list[DocumentTable] = filter_readable_documents(
            documents=await self.sql_repo.get_all(filters={"organization_id": organization_id}),
            user_role=user_role,
            get_document_type=lambda document: DocumentType(document.type),
        )
        document_ids = [document.id for document in documents if document.id is not None]
        service_items_by_document = {}

        if document_ids:
            service_items_by_document = await self.sql_repo.get_document_services_by_document_ids(document_ids=document_ids)

        return self.response_assembler.build_many(
            documents=documents,
            service_items_by_document=service_items_by_document,
        )

    async def get_document(self, id: int, organization_id: int, user_role: UserRole | None = None) -> DocumentResponse | None:
        """Returns one document if it belongs to the org."""
        await self.sql_repo.sync_contract_states(organization_id=organization_id)
        document = await self.sql_repo.get_by_id(id)
        if document is None or document.organization_id != organization_id:
            return None
        if not can_read_document_type(user_role=user_role, document_type=DocumentType(document.type)):
            return None

        return await self.response_assembler.build(document=document)
