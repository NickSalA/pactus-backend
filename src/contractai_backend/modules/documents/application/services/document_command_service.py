"""DocumentCommandService: orchestrates document writes and file access."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from ...api.schemas import CreateDocumentRequest, DocumentResponse, DocumentServiceItemRequest, FileRequest, UpdateDocumentRequest
from ...domain import DocumentTable, validate_service_currency_alignment, validate_service_periods
from ...domain.exceptions import (
    DocumentExtractionError,
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTransactionError,
    InvalidDocumentFileError,
)
from ..repositories import (
    DocumentChunkEnricher,
    DocumentCommandRepository,
    DocumentExtractor,
    DocumentQueryRepository,
    DocumentStorageRepository,
    ServiceCatalogRepository,
    VectorRepository,
)
from .document_command_policy import DocumentCommandPolicy
from .document_response_assembler import DocumentResponseAssembler


@dataclass
class DocumentUpdatePayload:
    """Carries normalized data required by document updates."""

    service_items_provided: bool
    requested_service_items: list[DocumentServiceItemRequest]
    validated_document: DocumentTable


class DocumentCommandService:
    def __init__(  # noqa: PLR0913
        self,
        command_repo: DocumentCommandRepository,
        query_repo: DocumentQueryRepository,
        service_repo: ServiceCatalogRepository,
        vector_repo: VectorRepository,
        extractor: DocumentExtractor,
        storage_repo: DocumentStorageRepository,
        chunk_enricher: DocumentChunkEnricher,
    ):
        """Stores dependencies needed by document commands."""
        self.command_repo = command_repo
        self.query_repo = query_repo
        self.service_repo = service_repo
        self.vector_repo = vector_repo
        self.extractor = extractor
        self.storage_repo = storage_repo
        self.chunk_enricher = chunk_enricher
        self.policy = DocumentCommandPolicy(service_repo=service_repo)
        self.response_assembler = DocumentResponseAssembler(sql_repo=query_repo)

    async def _get_document_entity(self, id: int, organization_id: int) -> DocumentTable | None:
        """Loads a document only if it belongs to the org."""
        document = await self.query_repo.get_by_id(id)
        if document is None or document.organization_id != organization_id:
            return None
        return document

    async def create_document(
        self,
        data: CreateDocumentRequest,
        file_data: FileRequest,
        organization_id: int,
        index_name: str = "contracts_index",
    ) -> DocumentResponse:
        """Creates a document and syncs all external stores."""
        await self.policy.validate_requested_services(organization_id=organization_id, service_items=data.service_items)
        validate_service_currency_alignment(service_items=data.service_items)
        validate_service_periods(
            document_start_date=data.start_date,
            document_end_date=data.end_date,
            service_items=data.service_items,
        )

        normalized_form_data = self.policy.normalize_form_data(base_form_data=data.form_data, service_items=data.service_items)

        new_document = self.policy.validate_document(
            {
                "name": data.name,
                "organization_id": organization_id,
                "client": data.client,
                "type": data.type,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "form_data": normalized_form_data,
                "state": data.state,
            }
        )

        parsed_document = await self.extractor.extract(file=file_data.content, filename=file_data.filename)
        if not parsed_document:
            raise DocumentExtractionError()

        self.chunk_enricher.enrich(chunks=parsed_document, organization_id=organization_id, form_data=normalized_form_data)

        saved_document = await self.command_repo.save(entity=new_document)
        if not saved_document.id:
            raise DocumentTransactionError(operation="create", details="Failed to save document in SQL, no ID returned")

        document_id = saved_document.id
        service_entities = self.policy.build_document_service_entities(document_id=document_id, service_items=data.service_items)

        storage_path = None
        vectors_added = False

        try:
            persisted_service_entities = await self.command_repo.replace_document_services(document_id=document_id, service_items=service_entities)

            storage_path = await self.storage_repo.upload_file(
                document_id=document_id,
                file=file_data.content,
                filename=file_data.filename,
                content_type=file_data.content_type,
            )

            await self.vector_repo.add_vectors(index_name=index_name, document_id=document_id, chunks=parsed_document)
            vectors_added = True

            saved_document.file_path = storage_path
            saved_document.file_name = file_data.filename
            updated_document = await self.command_repo.update(entity=saved_document)
            return self.response_assembler.serialize(document=updated_document, service_items=persisted_service_entities)

        except Exception as exc:
            if vectors_added:
                try:
                    await self.vector_repo.delete_vectors(index_name=index_name, document_id=document_id)
                except Exception:
                    pass

            if storage_path:
                try:
                    await self.storage_repo.delete_file(path=storage_path)
                except Exception:
                    pass

            try:
                await self.command_repo.delete(id=document_id)
            except Exception:
                pass

            raise DocumentTransactionError(operation="create", details=str(object=exc)) from exc

    async def delete_document(self, id: int, organization_id: int, index_name: str = "contracts_index") -> bool:
        """Deletes a document from SQL, vector store and storage."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)

        try:
            await self.vector_repo.delete_vectors(index_name=index_name, document_id=id)
        except Exception as exc:
            raise DocumentTransactionError(operation="delete vectors", details=str(object=exc)) from exc

        if document.file_path:
            try:
                await self.storage_repo.delete_file(path=document.file_path)
            except Exception as exc:
                logger.exception(f"Failed to delete document file from storage: {exc!s}")

        return await self.command_repo.delete(id)

    async def _prepare_document_update(
        self,
        document: DocumentTable,
        data: UpdateDocumentRequest,
        organization_id: int,
    ) -> DocumentUpdatePayload:
        """Builds normalized data needed before persisting an update."""
        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        service_items_provided = "service_items" in update_data
        requested_service_items = data.service_items or []

        if service_items_provided:
            await self.policy.validate_requested_services(
                organization_id=organization_id,
                service_items=requested_service_items,
            )
            validate_service_currency_alignment(service_items=requested_service_items)

        final_start_date = update_data.get("start_date", document.start_date)
        final_end_date = update_data.get("end_date", document.end_date)
        final_form_data = update_data.get("form_data", document.form_data)

        if service_items_provided:
            validate_service_periods(
                document_start_date=final_start_date,
                document_end_date=final_end_date,
                service_items=requested_service_items,
            )
            final_form_data = self.policy.normalize_form_data(
                base_form_data=final_form_data,
                service_items=requested_service_items,
            )

        validated_document = self.policy.validate_document(
            {
                "id": document.id,
                "organization_id": document.organization_id,
                "name": update_data.get("name", document.name),
                "client": update_data.get("client", document.client),
                "type": update_data.get("type", document.type),
                "start_date": final_start_date,
                "end_date": final_end_date,
                "form_data": final_form_data,
                "state": update_data.get("state", document.state),
                "file_path": document.file_path,
                "file_name": document.file_name,
                "created_at": document.created_at,
                "updated_at": datetime.now(UTC),
            }
        )

        return DocumentUpdatePayload(
            service_items_provided=service_items_provided,
            requested_service_items=requested_service_items,
            validated_document=validated_document,
        )

    @staticmethod
    def _apply_document_updates(document: DocumentTable, validated_document: DocumentTable) -> None:
        """Copies validated fields into the loaded document entity."""
        document.name = validated_document.name
        document.client = validated_document.client
        document.type = validated_document.type
        document.start_date = validated_document.start_date
        document.end_date = validated_document.end_date
        document.form_data = validated_document.form_data
        document.state = validated_document.state
        document.updated_at = validated_document.updated_at

    async def _replace_document_services_if_needed(
        self,
        document_id: int | None,
        payload: DocumentUpdatePayload,
    ) -> None:
        """Replaces linked service items when the request includes them."""
        if not payload.service_items_provided or document_id is None:
            return

        service_entities = self.policy.build_document_service_entities(
            document_id=document_id,
            service_items=payload.requested_service_items,
        )
        await self.command_repo.replace_document_services(document_id=document_id, service_items=service_entities)

    async def _update_document_without_file(
        self,
        document: DocumentTable,
        payload: DocumentUpdatePayload,
    ) -> DocumentResponse:
        """Persists an update when no file replacement is requested."""
        await self._replace_document_services_if_needed(document_id=document.id, payload=payload)
        updated_document = await self.command_repo.update(entity=document)
        return await self.response_assembler.build(document=updated_document)

    async def _extract_updated_chunks(
        self,
        file_data: FileRequest,
        organization_id: int,
        form_data: dict[str, Any],
    ) -> list[Any]:
        """Extracts and enriches chunks for a replacement file."""
        if not file_data.filename or file_data.content_type is None:
            raise InvalidDocumentFileError()

        parsed_document = await self.extractor.extract(file=file_data.content, filename=file_data.filename)
        if not parsed_document:
            raise DocumentExtractionError()

        self.chunk_enricher.enrich(chunks=parsed_document, organization_id=organization_id, form_data=form_data)
        return parsed_document

    async def _update_document_with_file(  # noqa: PLR0913
        self,
        id: int,
        document: DocumentTable,
        payload: DocumentUpdatePayload,
        file_data: FileRequest,
        organization_id: int,
        index_name: str,
    ) -> DocumentResponse:
        """Persists an update when the file content changes."""
        parsed_document = await self._extract_updated_chunks(
            file_data=file_data,
            organization_id=organization_id,
            form_data=document.form_data,
        )

        old_storage_path = document.file_path
        new_storage_path = None

        try:
            new_storage_path = await self.storage_repo.upload_file(
                document_id=id,
                file=file_data.content,
                filename=file_data.filename,
                content_type=file_data.content_type,
            )

            await self.vector_repo.add_vectors(index_name=index_name, document_id=id, chunks=parsed_document)

            document.file_path = new_storage_path
            document.file_name = file_data.filename
            document.updated_at = datetime.now(UTC)

            await self._replace_document_services_if_needed(document_id=document.id, payload=payload)

            updated_document = await self.command_repo.update(entity=document)

            if old_storage_path and old_storage_path != new_storage_path:
                try:
                    await self.storage_repo.delete_file(path=old_storage_path)
                except Exception:
                    pass

            return await self.response_assembler.build(document=updated_document)

        except Exception as exc:
            if new_storage_path:
                try:
                    await self.storage_repo.delete_file(path=new_storage_path)
                except Exception:
                    pass

            raise DocumentTransactionError(operation="update", details=str(object=exc)) from exc

    async def update_document(
        self,
        id: int,
        data: UpdateDocumentRequest,
        organization_id: int,
        file_data: FileRequest | None = None,
        index_name: str = "contracts_index",
    ) -> DocumentResponse:
        """Updates a document and refreshes external artifacts."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)

        payload = await self._prepare_document_update(document=document, data=data, organization_id=organization_id)
        self._apply_document_updates(document=document, validated_document=payload.validated_document)

        if file_data is None:
            return await self._update_document_without_file(document=document, payload=payload)

        return await self._update_document_with_file(
            id=id,
            document=document,
            payload=payload,
            file_data=file_data,
            organization_id=organization_id,
            index_name=index_name,
        )

    async def get_document_signed_url(self, id: int, organization_id: int, expires_in: int = 3600) -> str:
        """Returns a signed URL for a stored document file."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)
        if document.file_path is None:
            raise DocumentFileMissingError(document_id=id)

        return await self.storage_repo.create_signed_url(path=document.file_path, expires_in=expires_in)
