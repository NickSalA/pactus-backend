"""Tests unitarios para TemplateService."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from contractai_backend.core.exceptions.base import ValidationError
from contractai_backend.modules.documents.domain import DocumentType
import contractai_backend.modules.templates.application.services.template_service as template_service_module
from contractai_backend.modules.templates.application.services.template_service import TemplateService
from contractai_backend.modules.templates.domain.entities import TemplateContent, TemplateContractDateMapping, TemplateField, TemplateTable
from contractai_backend.modules.templates.domain.value_objs import TemplateState


class _FixedDateTime(datetime):
    @classmethod
    def now(cls):
        return cls(2026, 4, 13, 10, 30, 0)


def _make_template() -> TemplateTable:
    return TemplateTable(
        id=1,
        organization_id=1,
        name="Plantilla Empresa",
        document_type=DocumentType.COMPANY,
        content=TemplateContent(
            body_md="# Contrato\nHola {{cliente_nombre}}",
            fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
            version="1.0",
        ).model_dump(mode="python"),
        state=TemplateState.PUBLISHED,
    )


def _make_service(
    template_repo: AsyncMock | None = None,
    organization_repo: AsyncMock | None = None,
    renderer: AsyncMock | None = None,
    document_generator: AsyncMock | None = None,
    document_adapter: AsyncMock | None = None,
) -> TemplateService:
    return TemplateService(
        template_repo=template_repo or AsyncMock(),
        template_format_repo=AsyncMock(),
        organization_repo=organization_repo or AsyncMock(),
        renderer=renderer or AsyncMock(),
        document_generator=document_generator or AsyncMock(),
        document_adapter=document_adapter or AsyncMock(),
    )


class TestGenerateContract:
    @pytest.mark.asyncio
    async def test_generate_contract_uses_explicit_contract_date_mapping_with_custom_field_names(self, monkeypatch):
        monkeypatch.setattr(template_service_module, "datetime", _FixedDateTime)

        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = TemplateTable(
            id=1,
            organization_id=1,
            name="Plantilla Empresa",
            document_type=DocumentType.COMPANY,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}",
                fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
                operational_fields=[
                    TemplateField(key="fecha_vigencia_inicial_empresa", label="Inicio vigencia", type="date", required=True),
                    TemplateField(key="fecha_vigencia_final_empresa", label="Fin vigencia", type="date", required=True),
                ],
                contract_date_mapping=TemplateContractDateMapping(
                    start_date_field="fecha_vigencia_inicial_empresa",
                    end_date_field="fecha_vigencia_final_empresa",
                ),
                version="1.0",
            ).model_dump(mode="python"),
            state=TemplateState.PUBLISHED,
        )
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {"empresa_nombre": "ACME"}
        renderer = AsyncMock()
        renderer.render.return_value = "# Contrato renderizado"
        document_generator = AsyncMock()
        document_generator.generate_pdf.return_value = b"pdf"
        document_adapter = AsyncMock()
        document_adapter.save_generated_document.return_value = {"id": 456}
        service = _make_service(
            template_repo=template_repo,
            organization_repo=organization_repo,
            renderer=renderer,
            document_generator=document_generator,
            document_adapter=document_adapter,
        )

        result = await service.generate_contract(
            template_id=1,
            organization_id=1,
            form_data={
                "cliente_nombre": "ACME",
                "fecha_vigencia_inicial_empresa": "2026-01-01",
                "fecha_vigencia_final_empresa": "2026-12-31",
                "service_items": [{"service_id": 10, "start_date": "2026-01-01", "end_date": "2026-02-01"}],
            },
            user_role=None,
        )

        assert result == {"id": 456}
        document_payload = document_adapter.save_generated_document.await_args.kwargs["document_payload"]
        assert document_payload["start_date"] == "2026-01-01"
        assert document_payload["end_date"] == "2026-12-31"

    @pytest.mark.asyncio
    async def test_generate_contract_infers_contract_date_mapping_from_template_fields(self, monkeypatch):
        monkeypatch.setattr(template_service_module, "datetime", _FixedDateTime)

        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = TemplateTable(
            id=1,
            organization_id=1,
            name="Plantilla Empresa",
            document_type=DocumentType.COMPANY,
            content=TemplateContent(
                body_md="# Contrato\n{{ vigencia_inicio_real }}\n{{ vigencia_fin_real }}",
                fields=[
                    TemplateField(key="vigencia_inicio_real", label="Inicio de vigencia", type="date", required=True),
                    TemplateField(key="vigencia_fin_real", label="Fin de vigencia", type="date", required=True),
                ],
                version="1.0",
            ).model_dump(mode="python"),
            state=TemplateState.PUBLISHED,
        )
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {"empresa_nombre": "ACME"}
        renderer = AsyncMock()
        renderer.render.return_value = "# Contrato renderizado"
        document_generator = AsyncMock()
        document_generator.generate_pdf.return_value = b"pdf"
        document_adapter = AsyncMock()
        document_adapter.save_generated_document.return_value = {"id": 789}
        service = _make_service(
            template_repo=template_repo,
            organization_repo=organization_repo,
            renderer=renderer,
            document_generator=document_generator,
            document_adapter=document_adapter,
        )

        result = await service.generate_contract(
            template_id=1,
            organization_id=1,
            form_data={
                "cliente_nombre": "ACME",
                "vigencia_inicio_real": "2026-03-01",
                "vigencia_fin_real": "2026-12-31",
                "service_items": [{"service_id": 10, "start_date": "2026-03-01", "end_date": "2026-04-01"}],
            },
            user_role=None,
        )

        assert result == {"id": 789}
        document_payload = document_adapter.save_generated_document.await_args.kwargs["document_payload"]
        assert document_payload["start_date"] == "2026-03-01"
        assert document_payload["end_date"] == "2026-12-31"

    @pytest.mark.asyncio
    async def test_generate_contract_raises_when_service_items_do_not_expose_contract_dates(self, monkeypatch):
        monkeypatch.setattr(template_service_module, "datetime", _FixedDateTime)

        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = _make_template()
        organization_repo = AsyncMock()
        renderer = AsyncMock()
        document_generator = AsyncMock()
        document_adapter = AsyncMock()
        service = _make_service(
            template_repo=template_repo,
            organization_repo=organization_repo,
            renderer=renderer,
            document_generator=document_generator,
            document_adapter=document_adapter,
        )

        form_data = {
            "cliente_nombre": "ACME",
            "vigencia_inicio_real": "2026-01-01",
            "vigencia_fin_real": "2026-12-31",
            "service_items": [{"service_id": 10, "start_date": "2026-01-01", "end_date": "2026-02-01"}],
        }

        with pytest.raises(ValidationError, match="No se pudieron resolver las fechas de vigencia del contrato desde la plantilla"):
            await service.generate_contract(
                template_id=1,
                organization_id=1,
                form_data=form_data,
                user_role=None,
            )

        organization_repo.get_organization_data.assert_not_called()
        renderer.render.assert_not_called()
        document_generator.generate_pdf.assert_not_called()
        document_adapter.save_generated_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_contract_keeps_today_fallback_when_there_are_no_service_items(self, monkeypatch):
        monkeypatch.setattr(template_service_module, "datetime", _FixedDateTime)

        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = _make_template()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {"empresa_nombre": "ACME"}
        renderer = AsyncMock()
        renderer.render.return_value = "# Contrato renderizado"
        document_generator = AsyncMock()
        document_generator.generate_pdf.return_value = b"pdf"
        document_adapter = AsyncMock()
        document_adapter.save_generated_document.return_value = {"id": 123}
        service = _make_service(
            template_repo=template_repo,
            organization_repo=organization_repo,
            renderer=renderer,
            document_generator=document_generator,
            document_adapter=document_adapter,
        )

        result = await service.generate_contract(
            template_id=1,
            organization_id=1,
            form_data={"cliente_nombre": "ACME"},
            user_role=None,
        )

        assert result == {"id": 123}
        document_payload = document_adapter.save_generated_document.await_args.kwargs["document_payload"]
        assert document_payload["start_date"] == "2026-04-13"
        assert document_payload["end_date"] == "2026-04-13"
        assert document_payload["service_items"] == []

    @pytest.mark.asyncio
    async def test_generate_contract_raises_when_required_visible_field_is_empty(self, monkeypatch):
        monkeypatch.setattr(template_service_module, "datetime", _FixedDateTime)

        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = TemplateTable(
            id=1,
            organization_id=1,
            name="Plantilla Empresa",
            document_type=DocumentType.COMPANY,
            content=TemplateContent(
                body_md="# Contrato\nRUC: {{ ruc_empresa }}",
                fields=[TemplateField(key="ruc_empresa", label="RUC de La Empresa", required=False)],
                version="1.0",
            ).model_dump(mode="python"),
            state=TemplateState.PUBLISHED,
        )
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {"empresa_nombre": "ACME"}
        renderer = AsyncMock()
        document_generator = AsyncMock()
        document_adapter = AsyncMock()
        service = _make_service(
            template_repo=template_repo,
            organization_repo=organization_repo,
            renderer=renderer,
            document_generator=document_generator,
            document_adapter=document_adapter,
        )

        with pytest.raises(ValidationError, match="Faltan campos obligatorios.*RUC de La Empresa"):
            await service.generate_contract(
                template_id=1,
                organization_id=1,
                form_data={"ruc_empresa": "   "},
                user_role=None,
            )

        renderer.render.assert_not_called()
        document_generator.generate_pdf.assert_not_called()
        document_adapter.save_generated_document.assert_not_called()
