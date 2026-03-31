"""Tests unitarios para DocumentCommandService y servicios auxiliares."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.documents.application.dto import ContractQueryDTO
from contractai_backend.modules.documents.api.schemas import CreateDocumentRequest, DocumentServiceItemRequest, FileRequest, UpdateDocumentRequest
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


def _make_doc(
    id: int = 1,
    file_path: str | None = "docs/1/file.pdf",
    organization_id: int = 1,
    start_date: date | None = None,
    end_date: date | None = None,
    client: str = "Cliente Test",
    form_data: dict | None = None,
) -> DocumentTable:
    return DocumentTable(
        id=id,
        organization_id=organization_id,
        name="Contrato Test",
        client=client,
        type=DocumentType.LICENSES,
        start_date=start_date or date(2024, 1, 1),
        end_date=end_date or date(2024, 12, 31),
        form_data=form_data or {"value": 500.0, "currency": "USD", "owner": "IT"},
        state=DocumentState.ACTIVE,
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
) -> DocumentCommandService:
    relational_repo = sql_repo or AsyncMock()
    return DocumentCommandService(
        command_repo=relational_repo,
        query_repo=relational_repo,
        service_repo=relational_repo,
        vector_repo=vector_repo or AsyncMock(),
        extractor=extractor or AsyncMock(),
        storage_repo=storage_repo or AsyncMock(),
        chunk_enricher=VectorChunkMetadataEnricher(),
    )


def _make_query_service(sql_repo=None) -> DocumentQueryService:
    return DocumentQueryService(sql_repo=sql_repo or AsyncMock())


def _make_catalog_service(sql_repo=None) -> ServiceCatalogService:
    return ServiceCatalogService(sql_repo=sql_repo or AsyncMock())


def _make_contract_query_service(sql_repo=None) -> ContractQueryService:
    return ContractQueryService(sql_repo=sql_repo or AsyncMock())


def _create_request(service_items: list[DocumentServiceItemRequest] | None = None) -> CreateDocumentRequest:
    return CreateDocumentRequest(
        name="Contrato Test",
        client="Cliente Test",
        type=DocumentType.LICENSES,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        form_data={"value": 0.0, "currency": "USD", "owner": "IT"},
        service_items=service_items or [],
    )


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
        storage_repo.upload_file.assert_called_once()
        vector_repo.add_vectors.assert_called_once()
        sql_repo.update.assert_called_once()
        sql_repo.get_document_services.assert_not_called()

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

        service = _make_catalog_service(sql_repo=sql_repo)
        result = await service.list_services(organization_id=1)

        assert result == services
        sql_repo.get_services.assert_called_once_with(organization_id=1)


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
        vector_repo.delete_vectors.assert_called_once()
        storage_repo.delete_file.assert_called_once_with(path=doc.file_path)

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
        sql_repo.count_contracts.assert_any_call(organization_id=1, query=ContractQueryDTO(operation="count"))
        sql_repo.count_contracts.assert_any_call(
            organization_id=1,
            query=ContractQueryDTO(
                operation="count",
                max_value=50000,
                currency="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
            ),
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
            query=ContractQueryDTO(operation="list", client="Cliente", limit=5),
            limit=5,
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
            query=ContractQueryDTO(operation="ranking", currently_active=True, limit=10),
            limit=10,
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
