"""Tests unitarios para los routers de documentos con dependencias mockeadas."""

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.documents.api.dependencies import (
    get_contract_activity_service_for_documents,
    get_document_command_service,
    get_document_query_service,
    get_service_catalog_service,
)
from contractai_backend.modules.documents.api.routers import router
from contractai_backend.modules.catalog.domain.entities import ServiceTable
from contractai_backend.modules.documents.domain import DocumentTable
from contractai_backend.modules.documents.domain.exceptions import DocumentFileMissingError, DocumentNotFoundError
from contractai_backend.modules.documents.domain.value_objs import DocumentState, DocumentType
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(mock_document_service=None, mock_query_service=None, mock_catalog_service=None, mock_contract_activity_service=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/documents")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, organization_id=1)
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    if mock_document_service is not None:
        app.dependency_overrides[get_document_command_service] = lambda: mock_document_service
    if mock_query_service is not None:
        app.dependency_overrides[get_document_query_service] = lambda: mock_query_service
    if mock_catalog_service is not None:
        app.dependency_overrides[get_service_catalog_service] = lambda: mock_catalog_service
    if mock_contract_activity_service is not None:
        app.dependency_overrides[get_contract_activity_service_for_documents] = lambda: mock_contract_activity_service

    return app


def _make_doc(id: int = 1, file_path: str | None = "docs/1/file.pdf") -> DocumentTable:
    return DocumentTable(
        id=id,
        organization_id=1,
        name="Contrato Test",
        client="Cliente Test",
        type=DocumentType.COMPANY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        form_data={"value": 500.0, "currency": "USD", "owner": "IT"},
        state=DocumentState.ACTIVE,
        file_path=file_path,
        file_name="file.pdf",
    )


def _doc_form_data() -> str:
    return json.dumps(
        {
            "name": "Contrato Test",
            "client": "Cliente Test",
            "type": "COMPANY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "form_data": {"value": 500.0, "currency": "USD", "owner": "IT"},
            "service_items": [],
        }
    )


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_list_documents_returns_200(self):
        docs = [_make_doc(1), _make_doc(2)]
        mock_query_service = AsyncMock()
        mock_query_service.get_documents.return_value = docs

        app = _make_app(mock_query_service=mock_query_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/")

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["form_data"] == {"value": 500.0, "currency": "USD", "owner": "IT"}


class TestListServices:
    @pytest.mark.asyncio
    async def test_list_services_returns_200(self):
        mock_catalog_service = AsyncMock()
        mock_catalog_service.list_services.return_value = [ServiceTable(id=1, organization_id=1, name="Hosting")]

        app = _make_app(mock_catalog_service=mock_catalog_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/services")

        assert response.status_code == 200
        assert response.json() == [{"id": 1, "name": "Hosting"}]


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_get_document_returns_200(self):
        doc = _make_doc()
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = doc

        app = _make_app(mock_query_service=mock_query_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/1")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["type"] == "COMPANY"

    @pytest.mark.asyncio
    async def test_get_document_not_found_returns_404(self):
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = None

        app = _make_app(mock_query_service=mock_query_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/99")

        assert response.status_code == 404


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_document_returns_201(self):
        doc = _make_doc()
        mock_document_service = AsyncMock()
        mock_document_service.create_document.return_value = doc
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_contract_activity_service=mock_audit)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/",
                data={"document": _doc_form_data()},
                files={"file": ("file.pdf", b"pdf content", "application/pdf")},
            )

        assert response.status_code == 201
        assert response.json()["id"] == 1

    @pytest.mark.asyncio
    async def test_create_document_invalid_json_returns_400(self):
        mock_document_service = AsyncMock()
        mock_audit = AsyncMock()
        app = _make_app(mock_document_service=mock_document_service, mock_contract_activity_service=mock_audit)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/",
                data={"document": "not valid json"},
                files={"file": ("file.pdf", b"pdf content", "application/pdf")},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_document_accepts_missing_document_payload(self):
        doc = _make_doc()
        mock_document_service = AsyncMock()
        mock_document_service.create_document.return_value = doc
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_contract_activity_service=mock_audit)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/documents/",
                files={"file": ("file.pdf", b"pdf content", "application/pdf")},
            )

        assert response.status_code == 201
        assert response.json()["id"] == 1


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_document_returns_204(self):
        mock_document_service = AsyncMock()
        mock_document_service.delete_document.return_value = True
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = _make_doc()
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_query_service=mock_query_service, mock_contract_activity_service=mock_audit)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/documents/1")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_document_not_found_returns_404(self):
        mock_document_service = AsyncMock()
        mock_document_service.delete_document.side_effect = DocumentNotFoundError(document_id=99)
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = _make_doc()
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_query_service=mock_query_service, mock_contract_activity_service=mock_audit)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/documents/99")

        assert response.status_code == 404


class TestGetDocumentFileUrl:
    @pytest.mark.asyncio
    async def test_get_file_url_returns_200(self):
        mock_document_service = AsyncMock()
        mock_document_service.get_document_signed_url.return_value = "https://storage/signed-url"

        app = _make_app(mock_document_service=mock_document_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/1/file-url")

        assert response.status_code == 200
        assert response.json()["url"] == "https://storage/signed-url"

    @pytest.mark.asyncio
    async def test_get_file_url_no_file_returns_404(self):
        mock_document_service = AsyncMock()
        mock_document_service.get_document_signed_url.side_effect = DocumentFileMissingError(document_id=1)

        app = _make_app(mock_document_service=mock_document_service)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/documents/1/file-url")

        assert response.status_code == 404


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_update_document_returns_200(self):
        updated = _make_doc()
        updated.file_name = "Nombre Actualizado"

        mock_document_service = AsyncMock()
        mock_document_service.update_document.return_value = updated
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = _make_doc()
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_query_service=mock_query_service, mock_contract_activity_service=mock_audit)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                "/documents/1",
                data={"document": json.dumps({"name": "Nombre Actualizado"})},
            )

        assert response.status_code == 200
        assert response.json()["file_name"] == "Nombre Actualizado"

    @pytest.mark.asyncio
    async def test_update_document_not_found_returns_404(self):
        mock_document_service = AsyncMock()
        mock_document_service.update_document.side_effect = DocumentNotFoundError(document_id=99)
        mock_query_service = AsyncMock()
        mock_query_service.get_document.return_value = _make_doc()
        mock_audit = AsyncMock()

        app = _make_app(mock_document_service=mock_document_service, mock_query_service=mock_query_service, mock_contract_activity_service=mock_audit)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                "/documents/99",
                data={"document": json.dumps({"name": "X"})},
            )

        assert response.status_code == 404
