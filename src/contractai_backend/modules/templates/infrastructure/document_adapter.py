"""Adaptador para conectar el módulo de plantillas con el módulo de documentos."""

from ...documents.api.schemas import CreateDocumentRequest, FileRequest
from ...documents.application.services import DocumentCommandService
from ..application.repositories.base_relational import IDocumentModuleAdapter


class DocumentModuleAdapter(IDocumentModuleAdapter):
    def __init__(self, doc_service: DocumentCommandService):
        self.doc_service = doc_service

    async def save_generated_document(self, document_payload: dict, file: bytes):
        """Implementación del método para guardar el documento generado."""
        doc_request = CreateDocumentRequest(
            name=document_payload["name"],
            client=document_payload["client"],
            type=document_payload["type"],
            start_date=document_payload["start_date"],
            end_date=document_payload["end_date"],
            form_data=document_payload["form_data"],
            state=document_payload.get("state"),
            service_items=document_payload.get("service_items", []),
        )

        file_request = FileRequest(filename=document_payload["file_name"], content=file, content_type="application/pdf")

        nuevo_documento = await self.doc_service.create_document(
            data=doc_request, file_data=file_request, organization_id=document_payload["organization_id"]
        )

        return nuevo_documento
