import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from contractai_backend.modules.integrations.application.repositories import ICloudIntegrationProvider, IDocumentIngestionTarget
from contractai_backend.modules.integrations.domain import (
    CloudFileNotFoundError,
    CloudStorageIntegrationError,
    InvalidCloudTokenError,
)


class IntegrationService:
    def __init__(self, provider: ICloudIntegrationProvider, ingestion_target: IDocumentIngestionTarget, index_name: str, contract_activity_service: Any = None):
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

    async def process_import(
        self,
        token: dict,
        files: list[dict[str, Any]],
        organization_id: int,
        imported_by_user_id: int | None = None,
        imported_by: dict[str, Any] | None = None,
    ) -> bool:
        logger.info(f"Iniciando importación directa. Organización: {organization_id}. Archivos: {len(files)}")
        token_is_valid = True

        total_files = len(files)

        for index, file_item in enumerate(files):
            file_id = str(file_item.get("file_id") or "").strip()
            document_payload = dict(file_item.get("document") or {})
            try:
                if not file_id:
                    raise ValueError("El archivo seleccionado no tiene un file_id válido.")

                metadata = await self.provider.get_file_metadata(token, file_id)
                file_name = self._resolve_filename(metadata=metadata, file_id=file_id)
                content_type = self._resolve_content_type(metadata=metadata)
                web_link = metadata.get("webViewLink", "")
                source_metadata = self._build_source_metadata(metadata=metadata, file_id=file_id, imported_by_user_id=imported_by_user_id)

                logger.debug(f"Extrayendo metadatos de: {file_name} | Link: {web_link}")

                file_bytes = await self.retrieve_file(token, file_id)
                created_document = await self.ingestion_target.ingest_drive_file(
                    document_payload=document_payload,
                    file_bytes=file_bytes,
                    filename=file_name,
                    content_type=content_type,
                    organization_id=organization_id,
                    source_metadata=source_metadata,
                    index_name=self.index_name,
                )

                if imported_by is not None and self.contract_activity_service is not None:
                    from contractai_backend.modules.audit.domain.value_objs import AuditContractAction
                    from contractai_backend.modules.users.domain.entities import UserTable

                    actor = UserTable(**imported_by)
                    state_val = str(created_document.state) if hasattr(created_document, "state") and created_document.state else None
                    await self.contract_activity_service.record(
                        action=AuditContractAction.IMPORTED_FROM_GOOGLE_DRIVE,
                        actor=actor,
                        document_id=getattr(created_document, "id", None),
                        document_name=getattr(created_document, "file_name", None),
                        document_type=getattr(created_document, "type", None),
                        state=state_val,
                    )

                logger.success(
                    f"¡Importación exitosa! Archivo: {file_name} | Tamaño: {len(file_bytes)} bytes | Documento: {getattr(created_document, 'id', None)}"
                )

                if index < total_files - 1:
                    await asyncio.sleep(1)

            except InvalidCloudTokenError as e:
                logger.error(f"Fallo de autenticación en la importación. Token inválido o expirado. Organización: {organization_id}. Error: {e}")
                token_is_valid = False
                break  # Si el token es inválido, abortamos todo el proceso para evitar un alud de errores
            except CloudFileNotFoundError as e:
                logger.warning(f"Archivo no encontrado {file_id}. Se saltará. Error: {e}")
                continue
            except CloudStorageIntegrationError as e:
                logger.error(f"Fallo al comunicarse con Google Drive para el archivo {file_id}. Error: {e}")
                continue
            except Exception as e:
                logger.error(f"Fallo crítico al importar el archivo {file_id}. Error: {e}")
                continue

        logger.info("Proceso de importación finalizado.")
        return token_is_valid
