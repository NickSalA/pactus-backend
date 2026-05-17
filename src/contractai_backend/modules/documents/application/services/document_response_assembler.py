"""Assembles document entities into API responses."""

from collections.abc import Mapping, Sequence

from ...api.schemas import CompanyContractResponse, DocumentResponse, DocumentServiceItemResponse, LaborContractResponse
from ...domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable
from ..repositories import DocumentQueryRepository


class DocumentResponseAssembler:
    def __init__(self, sql_repo: DocumentQueryRepository):
        """Stores the query repo used to load service items."""
        self.sql_repo: DocumentQueryRepository = sql_repo

    async def build(self, document: DocumentTable) -> DocumentResponse:
        """Builds one response including attached service items."""
        service_items: Sequence[CompanyContractServiceTable] = []
        company_contract: CompanyContractTable | None = None
        labor_contract: LaborContractTable | None = None
        if document.id is not None:
            company_contract = await self.sql_repo.get_company_contract_by_document_id(document_id=document.id)
            labor_contract = await self.sql_repo.get_labor_contract_by_document_id(document_id=document.id)
            service_items = await self.sql_repo.get_document_services(doc_id=document.id)

        return self.serialize(document=document, service_items=service_items, company_contract=company_contract, labor_contract=labor_contract)

    async def build_many(
        self,
        documents: Sequence[DocumentTable],
        service_items_by_document: Mapping[int, Sequence[CompanyContractServiceTable]] | None = None,
    ) -> list[DocumentResponse]:
        """Builds many responses from preloaded service items."""
        resolved_service_items = service_items_by_document or {}
        responses: list[DocumentResponse] = []

        for document in documents:
            service_items = resolved_service_items.get(document.id, []) if document.id is not None else []
            company_contract = await self.sql_repo.get_company_contract_by_document_id(document_id=document.id) if document.id is not None else None
            labor_contract = await self.sql_repo.get_labor_contract_by_document_id(document_id=document.id) if document.id is not None else None
            responses.append(
                self.serialize(
                    document=document,
                    service_items=service_items,
                    company_contract=company_contract,
                    labor_contract=labor_contract,
                )
            )

        return responses

    @staticmethod
    def serialize(
        document: DocumentTable,
        service_items: Sequence[CompanyContractServiceTable] | None = None,
        company_contract: CompanyContractTable | None = None,
        labor_contract: LaborContractTable | None = None,
    ) -> DocumentResponse:
        """Serializes a document entity into an API response."""
        resolved_service_items = list(service_items or [])

        return DocumentResponse(
            id=document.id,
            type=document.type,
            start_date=document.start_date,
            end_date=document.end_date,
            form_data=document.form_data or {},
            state=document.state,
            folder_id=document.folder_id,
            file_path=document.file_path,
            file_name=document.file_name,
            service_items=[DocumentServiceItemResponse.model_validate(item) for item in resolved_service_items],
            company_contract=CompanyContractResponse.model_validate(company_contract) if company_contract is not None else None,
            labor_contract=LaborContractResponse.model_validate(labor_contract) if labor_contract is not None else None,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
