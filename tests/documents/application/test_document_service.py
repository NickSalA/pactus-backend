"""Tests unitarios para DocumentCommandService y servicios auxiliares."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.documents.application.dto import (
    ContractQueryDTO,
    ExtractedDocumentData,
    ExtractedDocumentFormData,
    ExtractedDocumentServiceItem,
)
from contractai_backend.modules.documents.api.schemas import (
    CreateDocumentDraftRequest,
    CreateDocumentRequest,
    DocumentServiceItemRequest,
    FileRequest,
    UpdateDocumentRequest,
)
from contractai_backend.modules.documents.infrastructure.chunk_metadata_enricher import VectorChunkMetadataEnricher
from contractai_backend.modules.documents.application.services.contract_query_service import ContractQueryService
from contractai_backend.modules.documents.application.services.document_query_service import DocumentQueryService
from contractai_backend.modules.documents.application.services.document_command_service import DocumentCommandService
from contractai_backend.modules.documents.application.services.service_catalog_service import ServiceCatalogService
from contractai_backend.modules.documents.domain import DocumentServiceTable, DocumentTable, ServiceTable
from contractai_backend.modules.documents.domain.exceptions import (
    DocumentExtractionError,
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTransactionError,
    DocumentValidationError,
)
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentState, DocumentType
from contractai_backend.modules.users.domain.value_objs import UserRole

_UNSET = object()


def _make_doc(
    id: int = 1,
    file_path: str | None = "docs/1/file.pdf",
    organization_id: int = 1,
    start_date: date | None | object = _UNSET,
    end_date: date | None | object = _UNSET,
    client: str | None = "Cliente Test",
    form_data: dict | None = None,
    name: str | None = "Contrato Test",
    doc_type: DocumentType | None = DocumentType.COMPANY,
    state: DocumentState | None = DocumentState.ACTIVE,
) -> DocumentTable:
    return DocumentTable(
        id=id,
        organization_id=organization_id,
        name=name,
        client=client,
        type=doc_type,
        start_date=date(2024, 1, 1) if start_date is _UNSET else start_date,
        end_date=date(2024, 12, 31) if end_date is _UNSET else end_date,
        form_data=form_data or {"value": 500.0, "currency": "USD", "owner": "IT"},
        state=state,
        file_path=file_path,
        file_name="file.pdf",
    )


def _make_document_service(id: int = 1, document_id: int = 1, service_id: int = 2) -> DocumentServiceTable:
    return DocumentServiceTable(
        id=id,
        document_id=document_id,
        service_id=service_id,
        description="Hosting administrado",
        value=250.0,
        currency=CurrencyType.USD,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 4, 1),
    )


def _make_service(
    sql_repo=None,
    vector_repo=None,
    extractor=None,
    storage_repo=None,
    structured_extractor=None,
) -> DocumentCommandService:
    relational_repo = sql_repo or AsyncMock()
    relational_repo.sync_contract_states.return_value = 0
    resolved_structured_extractor = structured_extractor
    if resolved_structured_extractor is None:
        resolved_structured_extractor = AsyncMock()
        resolved_structured_extractor.extract.return_value = ExtractedDocumentData()
    return DocumentCommandService(
        command_repo=relational_repo,
        query_repo=relational_repo,
        service_repo=relational_repo,
        vector_repo=vector_repo or AsyncMock(),
        extractor=extractor or AsyncMock(),
        structured_extractor=resolved_structured_extractor,
        storage_repo=storage_repo or AsyncMock(),
        chunk_enricher=VectorChunkMetadataEnricher(),
    )


def _make_query_service(sql_repo=None) -> DocumentQueryService:
    relational_repo = sql_repo or AsyncMock()
    relational_repo.sync_contract_states.return_value = 0
    return DocumentQueryService(sql_repo=relational_repo)


def _make_catalog_service(sql_repo=None) -> ServiceCatalogService:
    return ServiceCatalogService(sql_repo=sql_repo or AsyncMock())


def _make_contract_query_service(sql_repo=None) -> ContractQueryService:
    relational_repo = sql_repo or AsyncMock()
    relational_repo.sync_contract_states.return_value = 0
    return ContractQueryService(sql_repo=relational_repo)


def _create_request(service_items: list[DocumentServiceItemRequest] | None = None) -> CreateDocumentRequest:
    return CreateDocumentRequest(
        name="Contrato Test",
        client="Cliente Test",
        type=DocumentType.COMPANY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        form_data={"value": 0.0, "currency": "USD", "owner": "IT"},
        service_items=service_items or [],
    )


def _create_draft_request(**overrides) -> CreateDocumentDraftRequest:
    payload = {
        "form_data": {},
        "service_items": [],
    }
    payload.update(overrides)
    return CreateDocumentDraftRequest(**payload)


def _file_request() -> FileRequest:
    return FileRequest(content=b"pdf content", filename="file.pdf", content_type="application/pdf")


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_document_success(self):
        saved = _make_doc()
        updated = _make_doc(file_path="docs/1/file.pdf")

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        vector_repo = AsyncMock()
        extractor = AsyncMock()
        extractor.extract.return_value = ["chunk1", "chunk2"]

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(sql_repo, vector_repo, extractor, storage_repo)
        result = await service.create_document(_create_request(), _file_request(), organization_id=1)

        assert result.id == updated.id
        assert result.file_path == updated.file_path
        sql_repo.save.assert_called_once()
        sql_repo.replace_document_services.assert_called_once()
        sql_repo.sync_contract_states.assert_called_once_with(organization_id=1)
        storage_repo.upload_file.assert_called_once()
        vector_repo.add_vectors.assert_called_once()
        sql_repo.update.assert_called_once()
        sql_repo.get_document_services.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_document_autofills_missing_fields_from_extraction(self):
        saved = _make_doc(
            name="Contrato Estándar de Trabajador - Ana Perez",
            client="Ana Perez",
            doc_type=DocumentType.LABOR,
            state=DocumentState.DRAFT,
        )
        updated = _make_doc(
            file_path="docs/1/file.pdf",
            name="Contrato Estándar de Trabajador - Ana Perez",
            client="Ana Perez",
            doc_type=DocumentType.LABOR,
            state=DocumentState.DRAFT,
        )

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            name="Contrato extraido",
            client="Institucion Convenio SAC",
            worker_name="Ana Perez",
            type=DocumentType.LABOR,
            labor_monthly_value=1200.0,
            labor_monthly_currency=CurrencyType.USD,
            form_data=ExtractedDocumentFormData(value=24000.0, currency=CurrencyType.USD),
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.name == "Contrato Estándar de Trabajador - Ana Perez"
        assert saved_entity.client == "Ana Perez"
        assert saved_entity.type == DocumentType.LABOR
        assert saved_entity.form_data["value"] == 1200.0
        assert saved_entity.form_data["currency"] == "USD"
        assert saved_entity.state == DocumentState.DRAFT

    @pytest.mark.asyncio
    async def test_create_document_labor_uses_nulls_when_worker_or_monthly_pay_are_not_explicit(self):
        saved = _make_doc(
            name="Contrato extraido",
            client=None,
            doc_type=DocumentType.LABOR,
            state=DocumentState.DRAFT,
            form_data={"value": None, "currency": None},
        )
        updated = _make_doc(
            file_path="docs/1/file.pdf",
            name="Contrato extraido",
            client=None,
            doc_type=DocumentType.LABOR,
            state=DocumentState.DRAFT,
            form_data={"value": None, "currency": None},
        )

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            name="Contrato extraido",
            client="Institucion Convenio SAC",
            type=DocumentType.LABOR,
            form_data=ExtractedDocumentFormData(value=24000.0, currency=CurrencyType.USD),
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.name == "Contrato extraido"
        assert saved_entity.client is None
        assert saved_entity.type == DocumentType.LABOR
        assert saved_entity.form_data["value"] is None
        assert saved_entity.form_data["currency"] is None

    @pytest.mark.asyncio
    async def test_create_document_company_uses_standard_company_contract_name_from_client(self):
        saved = _make_doc(
            name="Contrato Estándar de Empresa - Nova Gestión Integral Académica S.A.C.",
            client="Nova Gestión Integral Académica S.A.C.",
            doc_type=DocumentType.COMPANY,
            state=DocumentState.DRAFT,
        )
        updated = _make_doc(
            file_path="docs/1/file.pdf",
            name="Contrato Estándar de Empresa - Nova Gestión Integral Académica S.A.C.",
            client="Nova Gestión Integral Académica S.A.C.",
            doc_type=DocumentType.COMPANY,
            state=DocumentState.DRAFT,
        )

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            name="Contrato de prestación de servicios",
            client="Nova Gestión Integral Académica S.A.C.",
            type=DocumentType.COMPANY,
            start_date=date(2026, 3, 3),
            end_date=date(2026, 8, 31),
            form_data=ExtractedDocumentFormData(value=22900.0, currency=CurrencyType.PEN),
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.name == "Contrato Estándar de Empresa - Nova Gestión Integral Académica S.A.C."
        assert saved_entity.client == "Nova Gestión Integral Académica S.A.C."
        assert saved_entity.type == DocumentType.COMPANY
        assert saved_entity.form_data["value"] == 22900.0
        assert saved_entity.form_data["currency"] == "PEN"

    @pytest.mark.asyncio
    async def test_create_document_manual_fields_override_extraction(self):
        saved = _make_doc(name="Manual", client="Cliente manual", doc_type=DocumentType.COMPANY, state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf")

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            name="Extraido",
            client="Cliente extraido",
            type=DocumentType.LABOR,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 1),
            form_data=ExtractedDocumentFormData(value=1200.0, currency=CurrencyType.EUR),
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        request = _create_draft_request(
            name="Manual",
            client="Cliente manual",
            type=DocumentType.COMPANY,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 12, 31),
            form_data={"value": 900.0, "currency": "USD"},
            state=DocumentState.ACTIVE,
        )

        await service.create_document(request, _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.name == "Manual"
        assert saved_entity.client == "Cliente manual"
        assert saved_entity.type == DocumentType.COMPANY
        assert saved_entity.start_date == date(2024, 2, 1)
        assert saved_entity.end_date == date(2024, 12, 31)
        assert saved_entity.form_data["value"] == 900.0
        assert saved_entity.form_data["currency"] == "USD"
        assert saved_entity.state == DocumentState.ACTIVE

    @pytest.mark.asyncio
    async def test_create_document_uses_nulls_and_draft_when_no_metadata_is_found(self):
        saved = _make_doc(name=None, client=None, doc_type=None, start_date=None, end_date=None, state=DocumentState.DRAFT)
        updated = _make_doc(
            file_path="docs/1/file.pdf", name=None, client=None, doc_type=None, start_date=None, end_date=None, state=DocumentState.DRAFT
        )

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData()

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.name is None
        assert saved_entity.client is None
        assert saved_entity.type is None
        assert saved_entity.start_date is None
        assert saved_entity.end_date is None
        assert saved_entity.state == DocumentState.DRAFT
        assert saved_entity.form_data["value"] is None
        assert saved_entity.form_data["currency"] is None

    @pytest.mark.asyncio
    async def test_create_document_persists_extracted_service_items_when_complete_and_valid(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = [_make_document_service(document_id=1, service_id=2)]
        sql_repo.get_document_services.return_value = []
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            form_data=ExtractedDocumentFormData(value=1200.0, currency=CurrencyType.USD),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting administrado",
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                )
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        persisted_entities = sql_repo.replace_document_services.await_args.kwargs["service_items"]
        assert len(persisted_entities) == 1
        assert persisted_entities[0].service_id == 2
        assert saved_entity.form_data["value"] == 1200.0
        assert saved_entity.form_data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_create_document_uses_extracted_service_sum_when_contract_total_is_missing(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = [_make_document_service(document_id=1, service_id=2)]
        sql_repo.get_document_services.return_value = []
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            form_data=ExtractedDocumentFormData(value=None, currency=None),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting administrado",
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                )
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.form_data["value"] == 250.0
        assert saved_entity.form_data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_create_document_discards_invalid_extracted_service_items(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            form_data=ExtractedDocumentFormData(value=1200.0, currency=CurrencyType.USD),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting administrado",
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2023, 12, 1),
                    end_date=date(2024, 4, 1),
                )
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        persisted_entities = sql_repo.replace_document_services.await_args.kwargs["service_items"]
        assert persisted_entities == []
        assert saved_entity.form_data["value"] == 1200.0
        assert saved_entity.form_data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_create_document_discards_incomplete_extracted_service_items(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            form_data=ExtractedDocumentFormData(value=1200.0, currency=CurrencyType.USD),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting administrado",
                    value=250.0,
                    currency=None,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                )
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        persisted_entities = sql_repo.replace_document_services.await_args.kwargs["service_items"]
        assert persisted_entities == []
        assert saved_entity.form_data["value"] == 1200.0
        assert saved_entity.form_data["currency"] == "USD"
        sql_repo.get_services_by_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_document_discards_duplicated_extracted_service_ids(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            form_data=ExtractedDocumentFormData(value=1200.0, currency=CurrencyType.USD),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting base",
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                ),
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting extension",
                    value=350.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 5, 1),
                    end_date=date(2024, 8, 1),
                ),
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )

        await service.create_document(_create_draft_request(), _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        persisted_entities = sql_repo.replace_document_services.await_args.kwargs["service_items"]
        assert persisted_entities == []
        assert saved_entity.form_data["value"] == 1200.0
        assert saved_entity.form_data["currency"] == "USD"
        sql_repo.get_services_by_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_document_manual_service_items_override_extracted_service_items(self):
        saved = _make_doc(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)
        updated = _make_doc(file_path="docs/1/file.pdf", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), state=DocumentState.ACTIVE)

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = [_make_document_service(document_id=1, service_id=3)]
        sql_repo.get_document_services.return_value = []
        sql_repo.get_services_by_ids.return_value = [
            ServiceTable(id=2, organization_id=1, name="Hosting"),
            ServiceTable(id=3, organization_id=1, name="Mesa de ayuda"),
        ]

        extractor = AsyncMock()
        extractor.extract.return_value = [type("Chunk", (), {"text": "contenido"})()]

        structured_extractor = AsyncMock()
        structured_extractor.extract.return_value = ExtractedDocumentData(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            service_items=[
                ExtractedDocumentServiceItem(
                    service_id=2,
                    description="Hosting administrado",
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                )
            ],
        )

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(
            sql_repo=sql_repo,
            extractor=extractor,
            structured_extractor=structured_extractor,
            storage_repo=storage_repo,
        )
        request = _create_draft_request(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            service_items=[
                DocumentServiceItemRequest(
                    service_id=3,
                    value=500.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 3, 31),
                )
            ],
        )

        await service.create_document(request, _file_request(), organization_id=1)

        persisted_entities = sql_repo.replace_document_services.await_args.kwargs["service_items"]
        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert len(persisted_entities) == 1
        assert persisted_entities[0].service_id == 3
        assert saved_entity.form_data["value"] == 500.0
        assert saved_entity.form_data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_create_document_with_invalid_service_ids_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_services_by_ids.return_value = []

        service = _make_service(sql_repo=sql_repo)
        request = _create_request(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=10,
                    value=100.0,
                    currency=CurrencyType.PEN,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 2, 1),
                )
            ]
        )

        with pytest.raises(DocumentValidationError, match="no existen"):
            await service.create_document(request, _file_request(), organization_id=1)

    @pytest.mark.asyncio
    async def test_create_document_extraction_fails_raises(self):
        extractor = AsyncMock()
        extractor.extract.return_value = []

        service = _make_service(extractor=extractor)
        with pytest.raises(DocumentExtractionError):
            await service.create_document(_create_request(), _file_request(), organization_id=1)

    @pytest.mark.asyncio
    async def test_create_document_storage_fails_rollbacks_sql(self):
        saved = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.replace_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = ["chunk"]

        storage_repo = AsyncMock()
        storage_repo.upload_file.side_effect = Exception("storage down")

        service = _make_service(sql_repo=sql_repo, extractor=extractor, storage_repo=storage_repo)

        with pytest.raises(DocumentTransactionError):
            await service.create_document(_create_request(), _file_request(), organization_id=1)

        sql_repo.delete.assert_called_once_with(id=saved.id)

    @pytest.mark.asyncio
    async def test_create_document_vector_fails_rollbacks_storage_and_sql(self):
        saved = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.replace_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = ["chunk"]

        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        vector_repo = AsyncMock()
        vector_repo.add_vectors.side_effect = Exception("qdrant down")

        service = _make_service(sql_repo=sql_repo, vector_repo=vector_repo, extractor=extractor, storage_repo=storage_repo)

        with pytest.raises(DocumentTransactionError):
            await service.create_document(_create_request(), _file_request(), organization_id=1)

        storage_repo.delete_file.assert_called_once()
        sql_repo.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_document_recalculates_form_data_from_service_items(self):
        saved = _make_doc()
        updated = _make_doc(file_path="docs/1/file.pdf")

        sql_repo = AsyncMock()
        sql_repo.save.return_value = saved
        sql_repo.update.return_value = updated
        sql_repo.replace_document_services.return_value = []
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = ["chunk1"]
        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/file.pdf"

        service = _make_service(sql_repo=sql_repo, extractor=extractor, storage_repo=storage_repo)
        request = _create_request(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=2,
                    value=250.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 4, 1),
                )
            ]
        )

        await service.create_document(request, _file_request(), organization_id=1)

        saved_entity = sql_repo.save.await_args.kwargs["entity"]
        assert saved_entity.form_data["value"] == 250.0
        assert saved_entity.form_data["currency"] == "USD"
        sql_repo.get_document_services.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_document_with_service_dates_outside_contract_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]

        service = _make_service(sql_repo=sql_repo)
        request = _create_request(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=2,
                    value=100.0,
                    currency=CurrencyType.USD,
                    start_date=date(2023, 12, 1),
                    end_date=date(2024, 2, 1),
                )
            ]
        )

        with pytest.raises(DocumentValidationError, match="dentro del rango del contrato"):
            await service.create_document(request, _file_request(), organization_id=1)

    @pytest.mark.asyncio
    async def test_create_document_with_mixed_currencies_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_services_by_ids.return_value = [
            ServiceTable(id=2, organization_id=1, name="Hosting"),
            ServiceTable(id=3, organization_id=1, name="Soporte"),
        ]

        service = _make_service(sql_repo=sql_repo)
        request = _create_request(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=2,
                    value=100.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 2, 1),
                ),
                DocumentServiceItemRequest(
                    service_id=3,
                    value=120.0,
                    currency=CurrencyType.EUR,
                    start_date=date(2024, 2, 2),
                    end_date=date(2024, 3, 1),
                ),
            ]
        )

        with pytest.raises(DocumentValidationError, match="misma moneda"):
            await service.create_document(request, _file_request(), organization_id=1)


class TestGetDocuments:
    @pytest.mark.asyncio
    async def test_get_documents_returns_all(self):
        docs = [_make_doc(1), _make_doc(2)]
        sql_repo = AsyncMock()
        sql_repo.get_all.return_value = docs
        sql_repo.get_document_services_by_document_ids.return_value = {1: [], 2: []}

        service = _make_query_service(sql_repo=sql_repo)
        result = await service.get_documents(organization_id=1)

        assert [document.id for document in result] == [1, 2]
        sql_repo.get_all.assert_called_once_with(filters={"organization_id": 1})
        sql_repo.get_document_services_by_document_ids.assert_called_once_with(document_ids=[1, 2])

    @pytest.mark.asyncio
    async def test_get_document_returns_doc_for_same_org(self):
        doc = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.get_document_services.return_value = []

        service = _make_query_service(sql_repo=sql_repo)
        result = await service.get_document(1, organization_id=1)

        assert result is not None
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_get_document_other_org_returns_none(self):
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = _make_doc(organization_id=2)

        service = _make_query_service(sql_repo=sql_repo)
        result = await service.get_document(1, organization_id=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_services_returns_catalog(self):
        services = [ServiceTable(id=1, organization_id=1, name="Hosting")]
        sql_repo = AsyncMock()
        sql_repo.get_services.return_value = services
        sql_repo.count_documents_by_service_ids.return_value = {1: 0}

        service = _make_catalog_service(sql_repo=sql_repo)
        result = await service.list_services(organization_id=1)

        assert result[0].id == 1
        assert result[0].name == "Hosting"
        sql_repo.get_services.assert_called_once_with(organization_id=1, include_inactive=False)


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        doc = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.delete.return_value = True
        vector_repo = AsyncMock()
        storage_repo = AsyncMock()

        service = _make_service(sql_repo=sql_repo, vector_repo=vector_repo, storage_repo=storage_repo)
        result = await service.delete_document(1, organization_id=1)

        assert result is True
        assert vector_repo.delete_vectors.await_args_list == [
            ((), {"index_name": "contracts_index", "document_id": 1}),
            ((), {"index_name": "drive_contracts_index", "document_id": 1}),
        ]
        storage_repo.delete_file.assert_called_once_with(path=doc.file_path)

    @pytest.mark.asyncio
    async def test_delete_document_cleans_both_known_indexes_even_when_drive_is_primary(self):
        doc = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.delete.return_value = True
        vector_repo = AsyncMock()
        storage_repo = AsyncMock()

        service = _make_service(sql_repo=sql_repo, vector_repo=vector_repo, storage_repo=storage_repo)
        result = await service.delete_document(1, organization_id=1, index_name="drive_contracts_index")

        assert result is True
        assert vector_repo.delete_vectors.await_args_list == [
            ((), {"index_name": "drive_contracts_index", "document_id": 1}),
            ((), {"index_name": "contracts_index", "document_id": 1}),
        ]

    @pytest.mark.asyncio
    async def test_delete_document_not_found_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = None

        service = _make_service(sql_repo=sql_repo)
        with pytest.raises(DocumentNotFoundError):
            await service.delete_document(99, organization_id=1)


class TestContractQueryService:
    @pytest.mark.asyncio
    async def test_requires_currency_for_value_filters(self):
        sql_repo = AsyncMock()
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="count", max_value=50000),
        )

        assert result["status"] == "needs_clarification"
        sql_repo.count_contracts.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_no_data_when_org_has_no_contracts(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.return_value = 0
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(organization_id=1, query=ContractQueryDTO(operation="count"))

        assert result == {"status": "no_data", "message": "No hay contratos cargados para la organizacion actual."}

    @pytest.mark.asyncio
    async def test_counts_contracts_with_overlap_range(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [4, 2]
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(
                operation="count",
                max_value=50000,
                currency="usd",
                period_start="2024-01-01",
                period_end="2024-03-31",
            ),
        )

        assert result["status"] == "success"
        assert result["count"] == 2
        assert result["filters_applied"]["currency"] == "USD"
        sql_repo.count_contracts.assert_any_call(
            organization_id=1,
            query=ContractQueryDTO(operation="count", state=DocumentState.ACTIVE),
            chatbot_ready_only=True,
        )
        sql_repo.count_contracts.assert_any_call(
            organization_id=1,
            query=ContractQueryDTO(
                operation="count",
                max_value=50000,
                currency="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                state=DocumentState.ACTIVE,
            ),
            chatbot_ready_only=True,
        )

    @pytest.mark.asyncio
    async def test_lists_serialized_contracts(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [3, 1]
        sql_repo.search_contracts.return_value = [_make_doc()]
        sql_repo.get_document_services_by_document_ids.return_value = {1: [_make_document_service(document_id=1)]}
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=2, organization_id=1, name="Hosting")]
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="list", client="Cliente", limit=5),
        )

        assert result["status"] == "success"
        assert result["items"][0]["name"] == "Contrato Test"
        assert result["items"][0]["value"] == 500.0
        assert result["items"][0]["service_items"][0]["service_name"] == "Hosting"
        assert result["returned_items"] == 1
        sql_repo.search_contracts.assert_called_once_with(
            organization_id=1,
            query=ContractQueryDTO(operation="list", client="Cliente", limit=5, state=DocumentState.ACTIVE),
            limit=5,
            chatbot_ready_only=True,
        )

    @pytest.mark.asyncio
    async def test_lists_current_activity_from_today_range(self):
        today = date.today()
        active_document = _make_doc(
            start_date=today - timedelta(days=2),
            end_date=today + timedelta(days=5),
        )

        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [2, 1]
        sql_repo.search_contracts.return_value = [active_document]
        sql_repo.get_document_services_by_document_ids.return_value = {1: []}
        sql_repo.get_services_by_ids.return_value = []
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="list", currently_active=True),
        )

        assert result["items"][0]["is_currently_active"] is True
        assert result["filters_applied"]["currently_active"] is True
        assert result["filters_applied"]["state"] == DocumentState.ACTIVE

    @pytest.mark.asyncio
    async def test_returns_client_ranking(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [4, 4]
        sql_repo.rank_contracts_by_client.return_value = [
            {"client": "Cliente A", "currency": "USD", "total_value": 1500.0, "contracts_count": 3},
            {"client": "Cliente B", "currency": "USD", "total_value": 300.0, "contracts_count": 1},
        ]
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="ranking", currently_active=True, limit=10),
        )

        assert result["status"] == "success"
        assert result["items"][0]["client"] == "Cliente A"
        assert result["items"][0]["contracts_count"] == 3
        sql_repo.rank_contracts_by_client.assert_called_once_with(
            organization_id=1,
            query=ContractQueryDTO(operation="ranking", currently_active=True, limit=10, state=DocumentState.ACTIVE),
            limit=10,
            chatbot_ready_only=True,
        )

    @pytest.mark.asyncio
    async def test_defaults_chatbot_contract_queries_to_active_state(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [1, 1]
        sql_repo.search_contracts.return_value = [_make_doc()]
        sql_repo.get_document_services_by_document_ids.return_value = {1: []}
        sql_repo.get_services_by_ids.return_value = []
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(organization_id=1, query=ContractQueryDTO(operation="list"))

        assert result["filters_applied"]["state"] == DocumentState.ACTIVE
        sql_repo.search_contracts.assert_called_once_with(
            organization_id=1,
            query=ContractQueryDTO(operation="list", state=DocumentState.ACTIVE),
            limit=20,
            chatbot_ready_only=True,
        )

    @pytest.mark.asyncio
    async def test_respects_explicit_state_for_chatbot_contract_queries(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [1, 1]
        sql_repo.search_contracts.return_value = [_make_doc(state=DocumentState.DRAFT)]
        sql_repo.get_document_services_by_document_ids.return_value = {1: []}
        sql_repo.get_services_by_ids.return_value = []
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="list", state=DocumentState.DRAFT),
        )

        assert result["filters_applied"]["state"] == DocumentState.DRAFT
        sql_repo.search_contracts.assert_called_once_with(
            organization_id=1,
            query=ContractQueryDTO(operation="list", state=DocumentState.DRAFT),
            limit=20,
            chatbot_ready_only=True,
        )

    @pytest.mark.asyncio
    async def test_denies_queries_for_unreadable_document_type(self):
        sql_repo = AsyncMock()
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="list", document_type=DocumentType.COMPANY),
            user_role=UserRole.HR,
        )

        assert result == {"status": "forbidden", "message": "No tienes permisos para acceder a esa informacion."}
        sql_repo.count_contracts.assert_not_called()

    @pytest.mark.asyncio
    async def test_scopes_generic_queries_to_role_readable_type(self):
        sql_repo = AsyncMock()
        sql_repo.count_contracts.side_effect = [2, 1]
        sql_repo.search_contracts.return_value = [_make_doc(doc_type=DocumentType.LABOR)]
        sql_repo.get_document_services_by_document_ids.return_value = {1: []}
        sql_repo.get_services_by_ids.return_value = []
        service = _make_contract_query_service(sql_repo=sql_repo)

        result = await service.run_query(
            organization_id=1,
            query=ContractQueryDTO(operation="list"),
            user_role=UserRole.HR,
        )

        assert result["status"] == "success"
        assert result["filters_applied"]["document_type"] == DocumentType.LABOR
        sql_repo.search_contracts.assert_called_once_with(
            organization_id=1,
            query=ContractQueryDTO(operation="list", document_type=DocumentType.LABOR, state=DocumentState.ACTIVE),
            limit=20,
            chatbot_ready_only=True,
        )


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_update_document_without_file(self):
        doc = _make_doc()
        updated = _make_doc()
        updated.name = "Nuevo Nombre"

        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.update.return_value = updated
        sql_repo.get_document_services.return_value = []

        service = _make_service(sql_repo=sql_repo)
        result = await service.update_document(1, UpdateDocumentRequest(name="Nuevo Nombre"), organization_id=1)

        assert result.name == "Nuevo Nombre"
        sql_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_document_replaces_service_items_when_provided(self):
        doc = _make_doc()
        updated = _make_doc()

        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.update.return_value = updated
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=3, organization_id=1, name="Mesa de ayuda")]
        sql_repo.get_document_services.return_value = []

        service = _make_service(sql_repo=sql_repo)
        request = UpdateDocumentRequest(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=3,
                    value=500.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 3, 31),
                )
            ]
        )

        await service.update_document(1, request, organization_id=1)

        sql_repo.replace_document_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_document_recalculates_form_data_when_service_items_are_provided(self):
        doc = _make_doc()
        updated = _make_doc()

        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.update.return_value = updated
        sql_repo.get_services_by_ids.return_value = [ServiceTable(id=3, organization_id=1, name="Mesa de ayuda")]
        sql_repo.get_document_services.return_value = []

        service = _make_service(sql_repo=sql_repo)
        request = UpdateDocumentRequest(
            service_items=[
                DocumentServiceItemRequest(
                    service_id=3,
                    value=400.0,
                    currency=CurrencyType.USD,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 3, 31),
                )
            ]
        )

        await service.update_document(1, request, organization_id=1)

        updated_entity = sql_repo.update.await_args.kwargs["entity"]
        assert updated_entity.form_data["value"] == 400.0
        assert updated_entity.form_data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_update_document_not_found_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = None

        service = _make_service(sql_repo=sql_repo)
        with pytest.raises(DocumentNotFoundError):
            await service.update_document(99, UpdateDocumentRequest(name="X"), organization_id=1)

    @pytest.mark.asyncio
    async def test_update_document_with_file_success(self):
        doc = _make_doc()
        updated = _make_doc(file_path="docs/1/new.pdf")

        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        sql_repo.update.return_value = updated
        sql_repo.get_document_services.return_value = []

        extractor = AsyncMock()
        extractor.extract.return_value = ["chunk"]
        storage_repo = AsyncMock()
        storage_repo.upload_file.return_value = "docs/1/new.pdf"
        vector_repo = AsyncMock()

        service = _make_service(sql_repo=sql_repo, vector_repo=vector_repo, extractor=extractor, storage_repo=storage_repo)
        file_data = FileRequest(content=b"new pdf", filename="new.pdf", content_type="application/pdf")
        result = await service.update_document(1, UpdateDocumentRequest(), organization_id=1, file_data=file_data)

        assert result.file_path == "docs/1/new.pdf"
        storage_repo.delete_file.assert_called_once_with(path="docs/1/file.pdf")


class TestGetDocumentSignedUrl:
    @pytest.mark.asyncio
    async def test_returns_signed_url(self):
        doc = _make_doc()
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc
        storage_repo = AsyncMock()
        storage_repo.create_signed_url.return_value = "https://storage/signed"

        service = _make_service(sql_repo=sql_repo, storage_repo=storage_repo)
        url = await service.get_document_signed_url(1, organization_id=1)

        assert url == "https://storage/signed"

    @pytest.mark.asyncio
    async def test_document_not_found_raises(self):
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = None

        service = _make_service(sql_repo=sql_repo)
        with pytest.raises(DocumentNotFoundError):
            await service.get_document_signed_url(99, organization_id=1)

    @pytest.mark.asyncio
    async def test_document_without_file_raises(self):
        doc = _make_doc(file_path=None)
        sql_repo = AsyncMock()
        sql_repo.get_by_id.return_value = doc

        service = _make_service(sql_repo=sql_repo)
        with pytest.raises(DocumentFileMissingError):
            await service.get_document_signed_url(1, organization_id=1)
