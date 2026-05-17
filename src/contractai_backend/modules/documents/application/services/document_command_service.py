"""DocumentCommandService: orchestrates document writes and file access."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from .....core.exceptions.base import ForbiddenError
from ....folders.application.repositories import FolderRepository
from ....users.domain.value_objs import UserRole
from ...api.schemas import (
    CompanyContractRequest,
    CreateDocumentDraftRequest,
    CreateDocumentRequest,
    DocumentResponse,
    DocumentServiceItemRequest,
    FileRequest,
    LaborContractRequest,
    UpdateDocumentRequest,
)
from ..dto import ExtractedDocumentData
from ...domain import CompanyContractTable, DocumentTable, LaborContractTable, validate_service_currency_alignment, validate_service_periods
from ...domain.access_policy import can_manage_folder, can_read_document_type, can_write_document_type
from ...domain.value_objs import DocumentState, DocumentType
from ...domain.exceptions import (
    DocumentExtractionError,
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTransactionError,
    DocumentValidationError,
    InvalidDocumentFileError,
)
from ..repositories import (
    DocumentChunkEnricher,
    DocumentCommandRepository,
    DocumentExtractor,
    DocumentQueryRepository,
    DocumentStructuredExtractor,
    DocumentStorageRepository,
    VectorRepository,
)
from ....catalog.application.repositories import ServiceRepository
from .document_command_policy import DocumentCommandPolicy
from .document_response_assembler import DocumentResponseAssembler


@dataclass
class DocumentUpdatePayload:
    """Carries normalized data required by document updates."""

    service_items_provided: bool
    requested_service_items: list[DocumentServiceItemRequest]
    validated_document: DocumentTable


class DocumentCommandService:
    DEFAULT_VECTOR_INDEX_NAMES = ("contracts_index", "drive_contracts_index")
    LABOR_CONTRACT_NAME_PREFIX = "Contrato Estándar de Trabajador"
    COMPANY_CONTRACT_NAME_PREFIX = "Contrato Estándar de Empresa"

    def __init__(  # noqa: PLR0913
        self,
        command_repo: DocumentCommandRepository,
        query_repo: DocumentQueryRepository,
        service_repo: ServiceRepository,
        vector_repo: VectorRepository,
        extractor: DocumentExtractor,
        storage_repo: DocumentStorageRepository,
        chunk_enricher: DocumentChunkEnricher,
        folder_repo: FolderRepository | None = None,
        structured_extractor: DocumentStructuredExtractor | None = None,
    ):
        """Stores dependencies needed by document commands."""
        self.command_repo = command_repo
        self.query_repo = query_repo
        self.service_repo = service_repo
        self.folder_repo = folder_repo
        self.vector_repo = vector_repo
        self.extractor = extractor
        self.structured_extractor = structured_extractor
        self.storage_repo = storage_repo
        self.chunk_enricher = chunk_enricher
        self.policy = DocumentCommandPolicy(service_repo=service_repo)
        self.response_assembler = DocumentResponseAssembler(sql_repo=query_repo)

    async def _validate_folder_access(
        self,
        *,
        organization_id: int,
        folder_id: int | None,
        user_role: UserRole | None,
    ) -> None:
        """Ensures the requested folder belongs to the org and can be managed by the role."""
        if folder_id is None:
            return

        if self.folder_repo is None:
            raise DocumentValidationError(message="No se puede validar la carpeta solicitada en este entorno.")

        folder = await self.folder_repo.get_folder_by_id(folder_id)
        if folder is None or folder.organization_id != organization_id:
            raise DocumentValidationError(message="La carpeta seleccionada no existe en la organización actual.")
        if not can_manage_folder(user_role=user_role, owner_role=folder.owner_role):
            raise ForbiddenError("No tiene permisos para asignar esta carpeta")

    @staticmethod
    def _ensure_write_access(document_type: DocumentType, user_role: UserRole | None) -> None:
        """Raises when the role cannot mutate the given document type."""
        if not can_write_document_type(user_role=user_role, document_type=document_type):
            raise ForbiddenError("No tiene permisos para gestionar este tipo de contrato")

    @staticmethod
    def _can_read_document_kind(document_kind: DocumentType | None, user_role: UserRole | None) -> bool:
        """Returns whether the role can read the given document."""
        if document_kind is None:
            return True
        return can_read_document_type(user_role=user_role, document_type=document_kind)

    async def _get_document_kind(self, document_id: int | None) -> DocumentType | None:
        if document_id is None:
            return None
        kind = (await self.query_repo.get_contract_kinds_by_document_ids(document_ids=[document_id])).get(document_id)
        return DocumentType(kind) if kind is not None else None

    async def _get_document_entity(self, id: int, organization_id: int) -> DocumentTable | None:
        """Loads a document only if it belongs to the org."""
        document = await self.query_repo.get_by_id(id)
        if document is None or document.organization_id != organization_id:
            return None
        return document

    @staticmethod
    def _serialize_optional_enum(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _normalize_source_type(value: Any, form_data: dict[str, Any] | None = None) -> str:
        if isinstance(value, DocumentType):
            return "manual_upload"
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned.upper() not in {DocumentType.COMPANY.value, DocumentType.LABOR.value}:
                return cleaned

        source = (form_data or {}).get("source")
        if isinstance(source, dict) and source.get("provider"):
            return str(source["provider"]).strip() or "manual_upload"
        return "manual_upload"

    @staticmethod
    def _coerce_legacy_document_type(value: Any) -> DocumentType | None:
        if value is None:
            return None
        if isinstance(value, DocumentType):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in {DocumentType.COMPANY.value, DocumentType.LABOR.value}:
                return DocumentType(normalized)
        return None

    @classmethod
    def _resolve_contract_kind(
        cls,
        *,
        requested_contract_type: DocumentType | None,
        requested_type: Any,
        extracted_data: ExtractedDocumentData,
        user_role: UserRole | None,
    ) -> DocumentType | None:
        legacy_type = cls._coerce_legacy_document_type(requested_type)
        if requested_contract_type is not None:
            return requested_contract_type
        if legacy_type is not None:
            return legacy_type
        if extracted_data.type is not None:
            return extracted_data.type
        if user_role == UserRole.HR:
            return DocumentType.LABOR
        if user_role == UserRole.MANAGER:
            return DocumentType.COMPANY
        return None

    @staticmethod
    def _first_text_value(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _first_float_value(*values: Any) -> float | None:
        for value in values:
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @classmethod
    def _build_company_contract_entity(
        cls,
        *,
        document_id: int,
        data: CreateDocumentRequest | CreateDocumentDraftRequest | UpdateDocumentRequest,
        extracted_data: ExtractedDocumentData | None,
        form_data: dict[str, Any],
    ) -> CompanyContractTable:
        company_contract: CompanyContractRequest | None = getattr(data, "company_contract", None)
        return CompanyContractTable(
            document_id=document_id,
            ruc=cls._first_text_value(
                getattr(company_contract, "ruc", None),
                form_data.get("gerente_ruc"),
                form_data.get("contratista_ruc"),
                form_data.get("proveedor_ruc"),
                form_data.get("otra_parte_ruc"),
                form_data.get("ruc_gerente"),
                form_data.get("cliente_ruc"),
            ),
            client=cls._first_text_value(
                getattr(company_contract, "client", None),
                getattr(data, "client", None),
                extracted_data.client if extracted_data is not None else None,
            ),
            updated_at=datetime.now(UTC),
        )

    @classmethod
    def _build_labor_contract_entity(
        cls,
        *,
        document_id: int,
        data: CreateDocumentRequest | CreateDocumentDraftRequest | UpdateDocumentRequest,
        extracted_data: ExtractedDocumentData | None,
        form_data: dict[str, Any],
    ) -> LaborContractTable:
        labor_contract: LaborContractRequest | None = getattr(data, "labor_contract", None)
        salary_currency = getattr(labor_contract, "salary_currency", None) or cls._coerce_currency(form_data.get("currency"))
        return LaborContractTable(
            document_id=document_id,
            worker_name=cls._first_text_value(
                getattr(labor_contract, "worker_name", None),
                getattr(data, "client", None),
                extracted_data.worker_name if extracted_data is not None else None,
                form_data.get("trabajador_nombre"),
                form_data.get("nombre_trabajador"),
                form_data.get("trabajador_nombre_completo"),
                form_data.get("empleado_nombre_completo"),
            ),
            worker_document_number=cls._first_text_value(
                getattr(labor_contract, "worker_document_number", None),
                form_data.get("trabajador_dni"),
                form_data.get("dni_trabajador"),
                form_data.get("numero_documento_trabajador"),
                form_data.get("empleado_dni"),
            ),
            position=cls._first_text_value(
                getattr(labor_contract, "position", None),
                form_data.get("position"),
                form_data.get("puesto_trabajo"),
                form_data.get("cargo"),
                form_data.get("cargo_ocupar"),
            ),
            salary_value=cls._first_float_value(
                getattr(labor_contract, "salary_value", None),
                form_data.get("value"),
                form_data.get("monto_remuneracion"),
                form_data.get("remuneracion_mensual_monto"),
                form_data.get("remuneracion_bruta"),
            ),
            salary_currency=salary_currency,
            salary_periodicity=cls._first_text_value(
                getattr(labor_contract, "salary_periodicity", None),
                form_data.get("periodicidad_remuneracion"),
                form_data.get("frecuencia_pago"),
                form_data.get("periodicidad_pago"),
            ),
            contract_modality=cls._first_text_value(
                getattr(labor_contract, "contract_modality", None),
                form_data.get("modalidad_contrato"),
                form_data.get("modalidad_contrato_tipo"),
                form_data.get("forma_contratacion"),
            ),
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _coerce_currency(value: Any):
        if value is None or value == "":
            return None
        try:
            from ...domain import CurrencyType

            return CurrencyType(str(value).strip().upper())
        except ValueError:
            return None

    @classmethod
    def _build_labor_contract_name(cls, worker_name: str | None) -> str:
        normalized_worker_name = worker_name.strip() if isinstance(worker_name, str) else ""
        if normalized_worker_name:
            return f"{cls.LABOR_CONTRACT_NAME_PREFIX} - {normalized_worker_name}"
        return cls.LABOR_CONTRACT_NAME_PREFIX

    @classmethod
    def _build_company_contract_name(cls, company_name: str | None) -> str:
        normalized_company_name = company_name.strip() if isinstance(company_name, str) else ""
        if normalized_company_name:
            return f"{cls.COMPANY_CONTRACT_NAME_PREFIX} - {normalized_company_name}"
        return cls.COMPANY_CONTRACT_NAME_PREFIX

    @classmethod
    def _resolve_vector_index_names(cls, primary_index_name: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys((primary_index_name, *cls.DEFAULT_VECTOR_INDEX_NAMES)))

    @staticmethod
    def _resolve_extracted_client(*, extracted_data: ExtractedDocumentData, resolved_type: Any) -> str | None:
        if resolved_type == DocumentType.LABOR:
            return extracted_data.worker_name
        return extracted_data.client

    @classmethod
    def _resolve_document_name(
        cls,
        *,
        provided_name: str | None,
        extracted_data: ExtractedDocumentData,
        resolved_type: Any,
        resolved_client: str | None,
    ) -> str | None:
        if provided_name is not None:
            return provided_name

        if resolved_type == DocumentType.LABOR:
            worker_name = extracted_data.worker_name or resolved_client
            if worker_name is not None:
                return cls._build_labor_contract_name(worker_name=worker_name)

        if resolved_type == DocumentType.COMPANY and resolved_client is not None:
            return cls._build_company_contract_name(company_name=resolved_client)

        return extracted_data.name

    @classmethod
    def _apply_extracted_form_data(
        cls,
        *,
        normalized_form_data: dict[str, Any],
        extracted_data: ExtractedDocumentData,
        resolved_type: Any,
    ) -> dict[str, Any]:
        updated_form_data = dict(normalized_form_data)

        if resolved_type == DocumentType.LABOR:
            if updated_form_data.get("value") is None:
                updated_form_data["value"] = extracted_data.labor_monthly_value
            if updated_form_data.get("currency") is None:
                updated_form_data["currency"] = cls._serialize_optional_enum(extracted_data.labor_monthly_currency)
            return updated_form_data

        if updated_form_data.get("value") is None:
            updated_form_data["value"] = extracted_data.form_data.value
        if updated_form_data.get("currency") is None:
            updated_form_data["currency"] = cls._serialize_optional_enum(extracted_data.form_data.currency)
        return updated_form_data

    @staticmethod
    def _is_draft_request(data: CreateDocumentRequest | CreateDocumentDraftRequest) -> bool:
        return not isinstance(data, CreateDocumentRequest)

    async def _extract_structured_data(
        self,
        *,
        data: CreateDocumentRequest | CreateDocumentDraftRequest,
        filename: str,
        parsed_document: list[Any],
        organization_id: int,
    ) -> ExtractedDocumentData:
        if not self._is_draft_request(data) or self.structured_extractor is None:
            return ExtractedDocumentData()

        available_services = await self.service_repo.get_services(organization_id=organization_id)
        return await self.structured_extractor.extract(
            filename=filename,
            chunks=parsed_document,
            available_services=available_services,
        )

    async def _resolve_extracted_service_items(
        self,
        *,
        organization_id: int,
        extracted_data: ExtractedDocumentData,
        document_start_date: Any,
        document_end_date: Any,
    ) -> list[DocumentServiceItemRequest]:
        if document_start_date is None or document_end_date is None:
            return []

        candidates: list[DocumentServiceItemRequest] = []
        for item in extracted_data.service_items:
            if item.service_id is None or item.value is None or item.currency is None or item.start_date is None or item.end_date is None:
                continue

            candidates.append(
                DocumentServiceItemRequest(
                    service_id=item.service_id,
                    description=item.description,
                    value=item.value,
                    currency=item.currency,
                    start_date=item.start_date,
                    end_date=item.end_date,
                )
            )

        service_id_counts: dict[int, int] = {}
        for item in candidates:
            service_id_counts[item.service_id] = service_id_counts.get(item.service_id, 0) + 1

        duplicated_service_ids = {service_id for service_id, count in service_id_counts.items() if count > 1}
        if duplicated_service_ids:
            logger.debug(
                "Discarding duplicated extracted service_ids for document import: {}",
                sorted(duplicated_service_ids),
            )
            candidates = [item for item in candidates if item.service_id not in duplicated_service_ids]

        if not candidates:
            return []

        existing_services = await self.service_repo.get_services_by_ids(
            organization_id=organization_id,
            service_ids=sorted({item.service_id for item in candidates}),
        )
        existing_ids = {service.id for service in existing_services if service.id is not None}
        scoped_candidates = [item for item in candidates if item.service_id in existing_ids]

        valid_candidates: list[DocumentServiceItemRequest] = []
        for item in scoped_candidates:
            try:
                validate_service_periods(
                    document_start_date=document_start_date,
                    document_end_date=document_end_date,
                    service_items=[item],
                )
            except DocumentValidationError:
                continue
            valid_candidates.append(item)

        if not valid_candidates:
            return []

        try:
            validate_service_currency_alignment(service_items=valid_candidates)
        except DocumentValidationError:
            return []

        return valid_candidates

    async def _prepare_create_data(
        self,
        *,
        data: CreateDocumentRequest | CreateDocumentDraftRequest,
        organization_id: int,
        extracted_data: ExtractedDocumentData,
        user_role: UserRole | None,
    ) -> tuple[DocumentTable, list[DocumentServiceItemRequest], dict[str, Any], DocumentType | None]:
        is_draft_request = self._is_draft_request(data)
        resolved_type = self._resolve_contract_kind(
            requested_contract_type=data.contract_type,
            requested_type=data.type,
            extracted_data=extracted_data,
            user_role=user_role,
        )
        resolved_source_type = self._normalize_source_type(data.type, data.form_data)
        resolved_client = (
            data.client if data.client is not None else self._resolve_extracted_client(extracted_data=extracted_data, resolved_type=resolved_type)
        )
        resolved_name = self._resolve_document_name(
            provided_name=data.name,
            extracted_data=extracted_data,
            resolved_type=resolved_type,
            resolved_client=resolved_client,
        )
        resolved_start_date = data.start_date if data.start_date is not None else extracted_data.start_date
        resolved_end_date = data.end_date if data.end_date is not None else extracted_data.end_date
        resolved_state = data.state if data.state is not None else (DocumentState.DRAFT if is_draft_request else None)

        normalized_form_data = dict(data.form_data or {})
        normalized_form_data = self._apply_extracted_form_data(
            normalized_form_data=normalized_form_data,
            extracted_data=extracted_data,
            resolved_type=resolved_type,
        )

        manual_service_items = list(data.service_items)
        if manual_service_items and resolved_type != DocumentType.COMPANY:
            raise DocumentValidationError(message="Solo los contratos company pueden registrar servicios.")
        if manual_service_items:
            if resolved_start_date is None or resolved_end_date is None:
                raise DocumentValidationError(message="Las fechas del contrato son obligatorias cuando se registran servicios.")

            await self.policy.validate_requested_services(
                organization_id=organization_id,
                service_items=manual_service_items,
            )
            validate_service_currency_alignment(service_items=manual_service_items)
            validate_service_periods(
                document_start_date=resolved_start_date,
                document_end_date=resolved_end_date,
                service_items=manual_service_items,
            )
            resolved_service_items = manual_service_items
            normalized_form_data = self.policy.normalize_form_data(
                base_form_data=normalized_form_data,
                service_items=resolved_service_items,
            )
        else:
            resolved_service_items = []
            if resolved_type == DocumentType.COMPANY:
                resolved_service_items = await self._resolve_extracted_service_items(
                    organization_id=organization_id,
                    extracted_data=extracted_data,
                    document_start_date=resolved_start_date,
                    document_end_date=resolved_end_date,
                )
            if resolved_service_items and (normalized_form_data.get("value") is None or normalized_form_data.get("currency") is None):
                summarized_form_data = self.policy.normalize_form_data(
                    base_form_data=normalized_form_data,
                    service_items=resolved_service_items,
                )
                if normalized_form_data.get("value") is None:
                    normalized_form_data["value"] = summarized_form_data.get("value")
                if normalized_form_data.get("currency") is None:
                    normalized_form_data["currency"] = summarized_form_data.get("currency")

        if is_draft_request:
            normalized_form_data.setdefault("value", None)
            normalized_form_data.setdefault("currency", None)

        validated_document = self.policy.validate_document(
            {
                "name": resolved_name,
                "organization_id": organization_id,
                "client": resolved_client,
                "type": resolved_source_type,
                "start_date": resolved_start_date,
                "end_date": resolved_end_date,
                "form_data": normalized_form_data,
                "state": resolved_state,
                "folder_id": data.folder_id,
            }
        )
        return validated_document, resolved_service_items, normalized_form_data, resolved_type

    async def create_document(
        self,
        data: CreateDocumentRequest | CreateDocumentDraftRequest,
        file_data: FileRequest,
        organization_id: int,
        user_role: UserRole | None = None,
        index_name: str = "contracts_index",
    ) -> DocumentResponse:
        """Creates a document and syncs all external stores."""
        parsed_document = await self.extractor.extract(file=file_data.content, filename=file_data.filename)
        if not parsed_document:
            raise DocumentExtractionError()

        extracted_data = await self._extract_structured_data(
            data=data,
            filename=file_data.filename,
            parsed_document=parsed_document,
            organization_id=organization_id,
        )

        new_document, resolved_service_items, normalized_form_data, resolved_contract_kind = await self._prepare_create_data(
            data=data,
            organization_id=organization_id,
            extracted_data=extracted_data,
            user_role=user_role,
        )

        if resolved_contract_kind is None:
            raise DocumentValidationError(message="Debe indicar si el contrato es company o labor.")
        self._ensure_write_access(document_type=resolved_contract_kind, user_role=user_role)
        await self._validate_folder_access(
            organization_id=organization_id,
            folder_id=new_document.folder_id,
            user_role=user_role,
        )

        self.chunk_enricher.enrich(chunks=parsed_document, organization_id=organization_id, form_data=normalized_form_data)

        saved_document = await self.command_repo.save(entity=new_document)
        if not saved_document.id:
            raise DocumentTransactionError(operation="create", details="Failed to save document in SQL, no ID returned")

        document_id = saved_document.id
        saved_company_contract = None
        if resolved_contract_kind == DocumentType.COMPANY:
            saved_company_contract = await self.command_repo.upsert_company_contract(
                self._build_company_contract_entity(
                    document_id=document_id,
                    data=data,
                    extracted_data=extracted_data,
                    form_data=normalized_form_data,
                )
            )
        elif resolved_contract_kind == DocumentType.LABOR:
            await self.command_repo.upsert_labor_contract(
                self._build_labor_contract_entity(
                    document_id=document_id,
                    data=data,
                    extracted_data=extracted_data,
                    form_data=normalized_form_data,
                )
            )

        company_contract_id = saved_company_contract.id if saved_company_contract is not None else None
        service_entities = (
            self.policy.build_document_service_entities(company_contract_id=company_contract_id, service_items=resolved_service_items)
            if company_contract_id is not None
            else []
        )

        storage_path = None
        vectors_added = False

        try:
            persisted_service_entities = await self.command_repo.replace_document_services(doc_id=document_id, service_items=service_entities)

            storage_path = await self.storage_repo.upload_file(
                document_id=document_id,
                organization_id=saved_document.organization_id,
                document_type=resolved_contract_kind,
                file=file_data.content,
                filename=file_data.filename,
                content_type=file_data.content_type,
            )

            await self.vector_repo.add_vectors(index_name=index_name, document_id=document_id, chunks=parsed_document)
            vectors_added = True

            saved_document.file_path = storage_path
            saved_document.file_name = file_data.filename
            updated_document = await self.command_repo.update(entity=saved_document)
            await self.query_repo.sync_contract_states(organization_id=organization_id)
            refreshed_document = await self.query_repo.get_by_id(document_id)

            if not isinstance(refreshed_document, DocumentTable):
                return self.response_assembler.serialize(document=updated_document, service_items=persisted_service_entities)

            return self.response_assembler.serialize(document=refreshed_document, service_items=persisted_service_entities)

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

    async def delete_document(
        self,
        id: int,
        organization_id: int,
        user_role: UserRole | None = None,
        index_name: str = "contracts_index",
    ) -> bool:
        """Deletes a document from SQL, vector store and storage."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)
        document_kind = await self._get_document_kind(document.id)
        if document_kind is not None:
            self._ensure_write_access(document_type=document_kind, user_role=user_role)

        try:
            for vector_index_name in self._resolve_vector_index_names(primary_index_name=index_name):
                await self.vector_repo.delete_vectors(index_name=vector_index_name, document_id=id)
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
        user_role: UserRole | None,
    ) -> DocumentUpdatePayload:
        """Builds normalized data needed before persisting an update."""
        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        service_items_provided = "service_items" in update_data
        requested_service_items = data.service_items or []

        if "folder_id" in update_data:
            await self._validate_folder_access(
                organization_id=organization_id,
                folder_id=update_data["folder_id"],
                user_role=user_role,
            )

        if service_items_provided:
            await self.policy.validate_requested_services(
                organization_id=organization_id,
                service_items=requested_service_items,
            )
            validate_service_currency_alignment(service_items=requested_service_items)

        final_start_date = update_data.get("start_date", document.start_date)
        final_end_date = update_data.get("end_date", document.end_date)
        final_form_data = update_data.get("form_data", document.form_data)
        final_type = self._normalize_source_type(update_data.get("type", document.type), final_form_data)

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
                "type": final_type,
                "start_date": final_start_date,
                "end_date": final_end_date,
                "form_data": final_form_data,
                "state": update_data.get("state", document.state),
                "folder_id": update_data.get("folder_id", document.folder_id),
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
        document.type = validated_document.type
        document.start_date = validated_document.start_date
        document.end_date = validated_document.end_date
        document.form_data = validated_document.form_data
        document.state = validated_document.state
        document.folder_id = validated_document.folder_id
        document.updated_at = validated_document.updated_at

    async def _replace_document_services_if_needed(
        self,
        document_id: int | None,
        payload: DocumentUpdatePayload,
    ) -> None:
        """Replaces linked service items when the request includes them."""
        if not payload.service_items_provided or document_id is None:
            return

        company_contract = await self.query_repo.get_company_contract_by_document_id(document_id=document_id)
        if company_contract is None or company_contract.id is None:
            if payload.requested_service_items:
                raise DocumentValidationError(message="Solo los contratos company pueden registrar servicios.")
            await self.command_repo.replace_document_services(doc_id=document_id, service_items=[])
            return

        service_entities = self.policy.build_document_service_entities(
            company_contract_id=company_contract.id,
            service_items=payload.requested_service_items,
        )
        await self.command_repo.replace_document_services(doc_id=document_id, service_items=service_entities)

    async def _update_document_without_file(
        self,
        document: DocumentTable,
        payload: DocumentUpdatePayload,
        organization_id: int,
    ) -> DocumentResponse:
        """Persists an update when no file replacement is requested."""
        await self._replace_document_services_if_needed(document_id=document.id, payload=payload)
        updated_document = await self.command_repo.update(entity=document)
        await self.query_repo.sync_contract_states(organization_id=organization_id)

        if updated_document.id is not None:
            refreshed_document = await self.query_repo.get_by_id(updated_document.id)
            if isinstance(refreshed_document, DocumentTable):
                updated_document = refreshed_document

        return await self.response_assembler.build(document=updated_document)

    async def _upsert_contract_details_if_needed(
        self,
        *,
        document: DocumentTable,
        data: UpdateDocumentRequest,
        document_kind: DocumentType | None,
    ) -> None:
        if document.id is None:
            return
        form_data = document.form_data or {}
        if document_kind == DocumentType.COMPANY and (data.company_contract is not None or data.client is not None or data.form_data is not None):
            await self.command_repo.upsert_company_contract(
                self._build_company_contract_entity(document_id=document.id, data=data, extracted_data=None, form_data=form_data)
            )
        if document_kind == DocumentType.LABOR and (
            data.labor_contract is not None or data.client is not None or data.form_data is not None
        ):
            await self.command_repo.upsert_labor_contract(
                self._build_labor_contract_entity(document_id=document.id, data=data, extracted_data=None, form_data=form_data)
            )

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
        document_kind: DocumentType | None,
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
                organization_id=document.organization_id,
                document_type=document_kind,
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

            await self.query_repo.sync_contract_states(organization_id=organization_id)

            if updated_document.id is not None:
                refreshed_document = await self.query_repo.get_by_id(updated_document.id)
                if isinstance(refreshed_document, DocumentTable):
                    updated_document = refreshed_document

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
        user_role: UserRole | None = None,
        file_data: FileRequest | None = None,
        index_name: str = "contracts_index",
    ) -> DocumentResponse:
        """Updates a document and refreshes external artifacts."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)
        document_kind = await self._get_document_kind(document.id)
        if document_kind is not None:
            self._ensure_write_access(document_type=document_kind, user_role=user_role)
        if data.contract_type is not None:
            self._ensure_write_access(document_type=data.contract_type, user_role=user_role)

        payload = await self._prepare_document_update(
            document=document,
            data=data,
            organization_id=organization_id,
            user_role=user_role,
        )
        self._apply_document_updates(document=document, validated_document=payload.validated_document)
        await self._upsert_contract_details_if_needed(document=document, data=data, document_kind=document_kind)

        if file_data is None:
            return await self._update_document_without_file(
                document=document,
                payload=payload,
                organization_id=organization_id,
            )

        return await self._update_document_with_file(
            id=id,
            document=document,
            payload=payload,
            file_data=file_data,
            organization_id=organization_id,
            index_name=index_name,
            document_kind=document_kind,
        )

    async def get_document_signed_url(
        self,
        id: int,
        organization_id: int,
        user_role: UserRole | None = None,
        expires_in: int = 3600,
    ) -> str:
        """Returns a signed URL for a stored document file."""
        document = await self._get_document_entity(id=id, organization_id=organization_id)
        if not document:
            raise DocumentNotFoundError(document_id=id)
        document_kind = await self._get_document_kind(document.id)
        if not self._can_read_document_kind(document_kind=document_kind, user_role=user_role):
            raise DocumentNotFoundError(document_id=id)
        if document.file_path is None:
            raise DocumentFileMissingError(document_id=id)

        return await self.storage_repo.create_signed_url(path=document.file_path, expires_in=expires_in)
