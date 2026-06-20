from typing import Any

from ...documents.application.dto import CreateDocumentRequest, FileRequest
from ...documents.application.services import DocumentCommandService
from ...documents.domain import DocumentState
from ...users.domain.value_objs import UserRole
from ..application.repositories.base_relational import IDocumentModuleAdapter


class DocumentModuleAdapter(IDocumentModuleAdapter):
    def __init__(self, doc_service: DocumentCommandService):
        self.doc_service: DocumentCommandService = doc_service

    async def save_generated_document(self, document_payload: dict, file: bytes, user_role: UserRole | None, actor: Any | None = None):
        doc_request = CreateDocumentRequest(
            name=document_payload.get("name"),
            client=document_payload.get("client"),
            type=document_payload["type"],
            contract_type=document_payload.get("contract_type"),
            start_date=document_payload["start_date"],
            end_date=document_payload["end_date"],
            form_data=document_payload["form_data"],
            state=DocumentState(document_payload.get("state")),
            folder_id=document_payload.get("folder_id"),
            service_items=document_payload.get("service_items", []),
            company_contract=document_payload.get("company_contract"),
            labor_contract=document_payload.get("labor_contract"),
        )

        file_request = FileRequest(filename=document_payload["file_name"], content=file, content_type="application/pdf")

        nuevo_documento = await self.doc_service.create_document(
            data=doc_request,
            file_data=file_request,
            organization_id=document_payload["organization_id"],
            user_role=user_role,
        )

        return nuevo_documento
