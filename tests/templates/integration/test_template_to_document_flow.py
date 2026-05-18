"""Tests de integración para el flujo template -> document."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from contractai_backend.modules.documents.application.dto import CreateDocumentRequest, DocumentResponse, FileRequest
from contractai_backend.modules.documents.domain import DocumentState, DocumentType, CurrencyType
from contractai_backend.modules.templates.infrastructure.document_adapter import DocumentModuleAdapter


class TestTemplateToDocumentFlow:
    """Tests para verificar el flujo completo desde template hasta document."""

    @pytest.mark.asyncio
    async def test_adapter_correctly_transforms_template_payload_to_document_request(self):
        """
        Verifica que el DocumentModuleAdapter transforme correctamente
        el payload que viene de TemplateService al formato que espera DocumentCommandService.

        El payload de TemplateService tiene service_items como dicts con:
        - service_id, start_date, end_date (siempre)
        - value, currency (requeridos por DocumentServiceItemRequest)
        - description (opcional)
        """
        mock_doc_service = AsyncMock()
        mock_doc_service.create_document.return_value = MagicMock(
            id=1,
            name="Plantilla Empresa - Cliente",
            client="Cliente",
            type="company",
            state=DocumentState.PENDING_SIGNATURE,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

        adapter = DocumentModuleAdapter(doc_service=mock_doc_service)

        # Este es el payload exacto que genera TemplateService.generate_contract()
        template_payload = {
            "organization_id": 1,
            "template_id": 10,
            "name": "Plantilla Empresa - Cliente",
            "client": "Cliente",
            "type": "company_format",
            "contract_type": DocumentType.COMPANY,
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {
                "cliente_nombre": "Cliente",
                "empresa_nombre": "Mi Empresa S.A.",
                "value": 5000.00,
                "currency": "PEN",
            },
            "folder_id": None,
            "service_items": [
                {
                    "service_id": 5,
                    "description": "Servicio de desarrollo",
                    "value": 2500.00,
                    "currency": "PEN",
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-30",
                },
                {
                    "service_id": 8,
                    "description": "Servicio de diseño",
                    "value": 2500.00,
                    "currency": "PEN",
                    "start_date": "2026-07-01",
                    "end_date": "2026-12-31",
                },
            ],
            "file_name": "plantilla_empresa_cliente_1234567890.pdf",
        }

        result = await adapter.save_generated_document(
            document_payload=template_payload,
            file=b"fake_pdf_content",
            user_role=None,
        )

        # Verify the call was made correctly
        mock_doc_service.create_document.assert_called_once()
        call_kwargs = mock_doc_service.create_document.await_args.kwargs

        # Verify data argument
        data_arg = call_kwargs["data"]
        assert isinstance(data_arg, CreateDocumentRequest)
        assert data_arg.name == "Plantilla Empresa - Cliente"
        assert data_arg.client == "Cliente"
        assert data_arg.contract_type == DocumentType.COMPANY
        assert data_arg.state == DocumentState.PENDING_SIGNATURE

        # Verify service_items transformation
        assert len(data_arg.service_items) == 2
        first_item = data_arg.service_items[0]
        assert first_item.service_id == 5
        assert first_item.value == 2500.00
        assert first_item.currency == CurrencyType.PEN
        assert first_item.start_date == date(2026, 1, 1)
        assert first_item.end_date == date(2026, 6, 30)
        assert first_item.description == "Servicio de desarrollo"

        second_item = data_arg.service_items[1]
        assert second_item.service_id == 8
        assert second_item.value == 2500.00
        assert second_item.currency == CurrencyType.PEN

        # Verify file argument
        file_arg = call_kwargs["file_data"]
        assert isinstance(file_arg, FileRequest)
        assert file_arg.content == b"fake_pdf_content"
        assert file_arg.filename == "plantilla_empresa_cliente_1234567890.pdf"
        assert file_arg.content_type == "application/pdf"

        # Verify organization_id passed through
        assert call_kwargs["organization_id"] == 1
        assert call_kwargs["user_role"] is None

    @pytest.mark.asyncio
    async def test_adapter_handles_labor_contract_without_service_items(self):
        """Verifica que los contratos laborales (sin service_items) se manejan correctamente."""
        mock_doc_service = AsyncMock()
        mock_doc_service.create_document.return_value = MagicMock(
            id=2,
            name="Contrato Laboral - Juan Perez",
            client="Juan Perez",
            type="labor_format",
            state=DocumentState.PENDING_SIGNATURE,
        )

        adapter = DocumentModuleAdapter(doc_service=mock_doc_service)

        # Payload para contrato laboral - no debe tener service_items
        labor_payload = {
            "organization_id": 1,
            "template_id": 20,
            "name": "Contrato Laboral - Juan Perez",
            "client": "Juan Perez",
            "type": "labor_format",
            "contract_type": DocumentType.LABOR,
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-02-01",
            "end_date": "2027-02-01",
            "form_data": {
                "trabajador_nombre": "Juan Perez",
                "salary_value": 5000.00,
                "currency": "PEN",
            },
            "folder_id": None,
            "service_items": [],  # Labor contracts no tienen servicios
            "file_name": "contrato_laboral_juan_perez_1234567890.pdf",
        }

        result = await adapter.save_generated_document(
            document_payload=labor_payload,
            file=b"fake_pdf_content",
            user_role=None,
        )

        call_kwargs = mock_doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert isinstance(data_arg, CreateDocumentRequest)
        assert data_arg.service_items == []
        assert data_arg.contract_type == DocumentType.LABOR

    @pytest.mark.asyncio
    async def test_adapter_handles_missing_optional_fields_in_service_items(self):
        """Verifica que el adapter maneja service_items sin descripción opcional."""
        mock_doc_service = AsyncMock()
        mock_doc_service.create_document.return_value = MagicMock(id=3)

        adapter = DocumentModuleAdapter(doc_service=mock_doc_service)

        payload = {
            "organization_id": 1,
            "template_id": 30,
            "name": "Contrato Test",
            "client": "Cliente",
            "type": "company",
            "contract_type": DocumentType.COMPANY,
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {},
            "folder_id": None,
            "service_items": [
                {
                    "service_id": 10,
                    "value": 1000.00,
                    "currency": "USD",
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-31",
                    # description es opcional, no se incluye
                }
            ],
            "file_name": "test.pdf",
        }

        result = await adapter.save_generated_document(
            document_payload=payload,
            file=b"pdf",
            user_role=None,
        )

        call_kwargs = mock_doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert len(data_arg.service_items) == 1
        assert data_arg.service_items[0].service_id == 10
        assert data_arg.service_items[0].description is None  # Opcional

    @pytest.mark.asyncio
    async def test_adapter_preserves_folder_id_when_provided(self):
        """Verifica que folder_id se pasa correctamente cuando está presente."""
        mock_doc_service = AsyncMock()
        mock_doc_service.create_document.return_value = MagicMock(id=4, folder_id=5)

        adapter = DocumentModuleAdapter(doc_service=mock_doc_service)

        payload = {
            "organization_id": 1,
            "template_id": 40,
            "name": "Contrato Test",
            "client": "Cliente",
            "type": "company",
            "contract_type": DocumentType.COMPANY,
            "state": "PENDING_SIGNATURE",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "form_data": {},
            "folder_id": 5,  # Carpeta específica
            "service_items": [],
            "file_name": "test.pdf",
        }

        await adapter.save_generated_document(
            document_payload=payload,
            file=b"pdf",
            user_role=None,
        )

        call_kwargs = mock_doc_service.create_document.await_args.kwargs
        data_arg = call_kwargs["data"]

        assert data_arg.folder_id == 5
