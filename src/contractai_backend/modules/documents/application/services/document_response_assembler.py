"""Assembles document entities into API responses."""

from collections.abc import Mapping, Sequence

from ...api.schemas import DocumentResponse, DocumentServiceItemResponse
from ...domain import DocumentServiceTable, DocumentTable
from ..repositories import DocumentQueryRepository


class DocumentResponseAssembler:
    def __init__(self, sql_repo: DocumentQueryRepository):
        """Stores the query repo used to load service items."""
        self.sql_repo: DocumentQueryRepository = sql_repo

    async def build(self, document: DocumentTable) -> DocumentResponse:
        """Builds one response including attached service items."""
        service_items: Sequence[DocumentServiceTable] = []
        if document.id is not None:
            service_items: Sequence[DocumentServiceTable] = await self.sql_repo.get_document_services(doc_id=document.id)

        return self.serialize(document=document, service_items=service_items)

    def build_many(
        self,
        documents: Sequence[DocumentTable],
        service_items_by_document: Mapping[int, Sequence[DocumentServiceTable]] | None = None,
    ) -> list[DocumentResponse]:
        """Builds many responses from preloaded service items."""
        resolved_service_items = service_items_by_document or {}
        responses: list[DocumentResponse] = []

        for document in documents:
            service_items = resolved_service_items.get(document.id, []) if document.id is not None else []
            responses.append(self.serialize(document=document, service_items=service_items))

        return responses

    @staticmethod
    def serialize(
        document: DocumentTable,
        service_items: Sequence[DocumentServiceTable] | None = None,
    ) -> DocumentResponse:
        """Serializes a document entity into an API response."""
        resolved_service_items = list(service_items or [])

        return DocumentResponse(
            id=document.id,
            name=document.name,
            client=document.client,
            type=document.type,
            start_date=document.start_date,
            end_date=document.end_date,
            form_data=document.form_data,
            state=document.state,
            file_path=document.file_path,
            file_name=document.file_name,
            service_items=[DocumentServiceItemResponse.model_validate(item) for item in resolved_service_items],
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
