from datetime import UTC, datetime
from typing import Any

from ...documents.application.dto import CreateDocumentDraftRequest, FileRequest
from ...documents.application.services import DocumentCommandService
from ..application.repositories import IDocumentIngestionTarget


class DocumentIngestionAdapter(IDocumentIngestionTarget):
    def __init__(self, document_service: DocumentCommandService):
        self.document_service = document_service

    @staticmethod
    def _build_form_data(document_payload: dict[str, Any], source_metadata: dict[str, Any]) -> dict[str, Any]:
        form_data = dict(document_payload.get("form_data") or {})
        existing_source = dict(form_data.get("source") or {})
        form_data["source"] = {
            **existing_source,
            **source_metadata,
            "provider": "google_drive",
            "imported_at": datetime.now(tz=UTC).isoformat(),
        }
        return form_data

    async def ingest_drive_file(
        self,
        document_payload: dict[str, Any],
        file_bytes: bytes,
        filename: str,
        content_type: str,
        organization_id: int,
        source_metadata: dict[str, Any],
        index_name: str,
    ) -> Any:
        payload = dict(document_payload)
        payload["form_data"] = self._build_form_data(document_payload=document_payload, source_metadata=source_metadata)

        document_request = CreateDocumentDraftRequest(**payload)
        file_request = FileRequest(content=file_bytes, filename=filename, content_type=content_type)

        return await self.document_service.create_document(
            data=document_request,
            file_data=file_request,
            organization_id=organization_id,
            index_name=index_name,
        )
