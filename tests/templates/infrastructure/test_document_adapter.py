"""Tests para DocumentModuleAdapter."""

import pytest
from datetime import date
from unittest.mock import AsyncMock

from pactus_backend.modules.documents.application.dto import CreateDocumentRequest, FileRequest
from pactus_backend.modules.documents.application.services import DocumentCommandService
from pactus_backend.modules.documents.domain import DocumentState
from pactus_backend.modules.templates.infrastructure.document_adapter import DocumentModuleAdapter


class TestDocumentModuleAdapter:
    @pytest.mark.asyncio
    async def test_save_generated_document_passes_service_items_as_document_service_item_request(self):
        """Verifica que el adapter convierte correctamente los service_items."""
        doc_service = AsyncMock(spec=DocumentCommandService)
        doc_service.create_document.return_value = AsyncMock(id=123)

        adapter = DocumentModuleAdapter(doc_service=doc_service)

        document_payload = {
            "organization_id": 1,
            "template_id": 10,
            "name": "Contrato Test - Cliente",
            "client": "Cliente",
            "type": "company",
            "contract_type": "COMPANY",
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {"cliente_nombre": "Cliente"},
            "folder_id": None,
            "service_items": [
                {
                    "service_id": 10,
                    "value": 1500.00,
                    "currency": "PEN",
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-30",
                    "description": "Servicio de consultoría",
                }
            ],
            "file_name": "contrato_test_cliente.pdf",
        }

        result = await adapter.save_generated_document(
            document_payload=document_payload,
            file=b"pdf_content",
            user_role=None,
        )

        doc_service.create_document.assert_called_once()
        call_kwargs = doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert isinstance(data_arg, CreateDocumentRequest)
        assert len(data_arg.service_items) == 1
        service_item = data_arg.service_items[0]
        assert service_item.service_id == 10
        assert service_item.value == 1500.00
        assert service_item.currency.value == "PEN"
        assert service_item.start_date == date(2026, 1, 1)
        assert service_item.end_date == date(2026, 6, 30)
        assert service_item.description == "Servicio de consultoría"

    @pytest.mark.asyncio
    async def test_save_generated_document_passes_empty_service_items_for_labor_contract(self):
        """Verifica que labor contracts no pasan service_items."""
        doc_service = AsyncMock(spec=DocumentCommandService)
        doc_service.create_document.return_value = AsyncMock(id=456)

        adapter = DocumentModuleAdapter(doc_service=doc_service)

        document_payload = {
            "organization_id": 1,
            "template_id": 20,
            "name": "Contrato Laboral - Ana Torres",
            "client": "Ana Torres",
            "type": "labor",
            "contract_type": "LABOR",
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-02-01",
            "end_date": "2027-02-01",
            "form_data": {"trabajador_nombre": "Ana Torres", "salary_value": 5000},
            "folder_id": None,
            "service_items": [],
            "file_name": "contrato_laboral_ana_torres.pdf",
        }

        result = await adapter.save_generated_document(
            document_payload=document_payload,
            file=b"pdf_content",
            user_role=None,
        )

        doc_service.create_document.assert_called_once()
        call_kwargs = doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert isinstance(data_arg, CreateDocumentRequest)
        assert data_arg.service_items == []
        assert data_arg.contract_type.value == "LABOR"

    @pytest.mark.asyncio
    async def test_save_generated_document_uses_correct_document_state(self):
        """Verifica que el state se convierte correctamente a DocumentState enum."""
        doc_service = AsyncMock(spec=DocumentCommandService)
        doc_service.create_document.return_value = AsyncMock(id=789)

        adapter = DocumentModuleAdapter(doc_service=doc_service)

        document_payload = {
            "organization_id": 1,
            "template_id": 30,
            "name": "Contrato Test",
            "client": "Cliente",
            "type": "company",
            "contract_type": "COMPANY",
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {},
            "folder_id": None,
            "service_items": [],
            "file_name": "test.pdf",
        }

        await adapter.save_generated_document(
            document_payload=document_payload,
            file=b"pdf_content",
            user_role=None,
        )

        call_kwargs = doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert data_arg.state == DocumentState.PENDING_SIGNATURE
        assert isinstance(data_arg.state, DocumentState)

    @pytest.mark.asyncio
    async def test_save_generated_document_passes_file_correctly(self):
        """Verifica que el file se pasa como FileRequest."""
        doc_service = AsyncMock(spec=DocumentCommandService)
        doc_service.create_document.return_value = AsyncMock(id=999)

        adapter = DocumentModuleAdapter(doc_service=doc_service)

        document_payload = {
            "organization_id": 1,
            "template_id": 40,
            "name": "Contrato Test",
            "client": "Cliente",
            "type": "company",
            "contract_type": "COMPANY",
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {},
            "folder_id": None,
            "service_items": [],
            "file_name": "test.pdf",
        }
        pdf_bytes = b"fake_pdf_content"

        await adapter.save_generated_document(
            document_payload=document_payload,
            file=pdf_bytes,
            user_role=None,
        )

        call_kwargs = doc_service.create_document.await_args.kwargs
        file_arg = call_kwargs["file_data"]

        assert isinstance(file_arg, FileRequest)
        assert file_arg.content == pdf_bytes
        assert file_arg.filename == "test.pdf"
        assert file_arg.content_type == "application/pdf"
