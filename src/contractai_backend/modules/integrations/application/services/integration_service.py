import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from contractai_backend.modules.audit.application.services import ContractActivityService
from contractai_backend.modules.audit.domain.value_objs import AuditContractAction
from contractai_backend.modules.integrations.application.repositories import ICloudIntegrationProvider, IDocumentIngestionTarget
from contractai_backend.modules.integrations.domain import (
    InvalidIntegrationPayloadError,
)


class IntegrationService:
    def __init__(self, provider: ICloudIntegrationProvider, ingestion_target: IDocumentIngestionTarget, index_name: str, contract_activity_service: ContractActivityService | None = None):
        self.provider = provider
        self.ingestion_target = ingestion_target
        self.index_name = index_name
        self.contract_activity_service = contract_activity_service

    @staticmethod
    def _resolve_content_type(metadata: dict[str, Any]) -> str:
        mime_type = str(metadata.get("mimeType") or "")
        if mime_type.startswith("application/vnd.google-apps."):
            return "application/pdf"
        return mime_type or "application/octet-stream"

    @classmethod
    def _resolve_filename(cls, metadata: dict[str, Any], file_id: str) -> str:
        filename = str(metadata.get("name") or file_id).strip() or file_id
        content_type = cls._resolve_content_type(metadata)
        if content_type == "application/pdf" and Path(filename).suffix.lower() != ".pdf":
            return f"{filename}.pdf"
        return filename

    @staticmethod
    def _build_source_metadata(metadata: dict[str, Any], file_id: str, imported_by_user_id: int | None) -> dict[str, Any]:
        source_metadata: dict[str, Any] = {
            "file_id": file_id,
            "mime_type": metadata.get("mimeType"),
            "web_view_link": metadata.get("webViewLink"),
        }
        if imported_by_user_id is not None:
            source_metadata["imported_by_user_id"] = imported_by_user_id
        return source_metadata

    def get_authorization_url(self) -> str:
        return self.provider.get_auth_url()

    async def authenticate(self, code: str) -> dict:
        return await self.provider.exchange_code_for_token(code)

    async def retrieve_file(self, token: dict, file_id: str) -> bytes:
        return await self.provider.download_file(token, file_id)

    async def _build_actor(self, imported_by: dict[str, Any] | None) -> SimpleNamespace | None:
        return None if imported_by is None else SimpleNamespace(**imported_by)

    async def _ingest_single_file(
        self,
        *,
        token: dict,
        file_item: dict[str, Any],
        organization_id: int,
        imported_by_user_id: int | None,
        imported_by: dict[str, Any] | None,
        index: int,
        total_files: int,
    ) -> bool:
        file_id = str(file_item.get("file_id") or "").strip()
        document_payload = dict(file_item.get("document") or {})

        if not file_id:
            raise InvalidIntegrationPayloadError("El archivo seleccionado no tiene un file_id válido.")

        metadata = await self.provider.get_file_metadata(token, file_id)
        file_name = self._resolve_filename(metadata=metadata, file_id=file_id)
        content_type = self._resolve_content_type(metadata=metadata)
        source_metadata = self._build_source_metadata(
            metadata=metadata,
            file_id=file_id,
            imported_by_user_id=imported_by_user_id,
        )

        actor = await self._build_actor(imported_by)

        file_bytes = await self.retrieve_file(token, file_id)
        created_document = await self.ingestion_target.ingest_drive_file(
            document_payload=document_payload,
            file_bytes=file_bytes,
            filename=file_name,
            content_type=content_type,
            organization_id=organization_id,
            source_metadata=source_metadata,
            index_name=self.index_name,
            actor=actor,
        )

        if self.contract_activity_service is not None and actor is not None:
            await self.contract_activity_service.record(
                action=AuditContractAction.IMPORTED_FROM_GOOGLE_DRIVE,
                actor=actor,
                document_id=getattr(created_document, "id", None),
                document_name=file_name,
                document_type=document_payload.get("contract_type"),
                state=getattr(created_document, "state", None),
            )

        if index < total_files - 1:
            await asyncio.sleep(1)

        return True

    async def process_import(
        self,
        token: dict,
        files: list[dict[str, Any]],
        organization_id: int,
        imported_by_user_id: int | None = None,
        imported_by: dict[str, Any] | None = None,
    ) -> None:
        total_files = len(files)
        for index, file_item in enumerate(files):
            await self._ingest_single_file(
                token=token,
                file_item=file_item,
                organization_id=organization_id,
                imported_by_user_id=imported_by_user_id,
                imported_by=imported_by,
                index=index,
                total_files=total_files,
            )
