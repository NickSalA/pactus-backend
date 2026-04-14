"""Tests unitarios para TemplateAuthoringService."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.templates.api.schemas import GenerateTemplateDraftRequest, PreviewTemplateRequest, TemplateDraftResponse
from contractai_backend.modules.templates.application.services.template_authoring_service import TemplateAuthoringService
from contractai_backend.modules.templates.domain.entities import TemplateContent, TemplateField, TemplateFormatTable, TemplateTable
from contractai_backend.modules.templates.domain.value_objs import TemplateGenerationMode, TemplateState
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_format(document_type: DocumentType = DocumentType.COMPANY) -> TemplateFormatTable:
    return TemplateFormatTable(
        id=1,
        document_type=document_type,
        format_code="base_company" if document_type == DocumentType.COMPANY else "base_labor",
        label="Base Company" if document_type == DocumentType.COMPANY else "Base Labor",
        default_name="Plantilla Base",
    )


def _make_authoring_service(
    template_repo: AsyncMock | None = None,
    template_format_repo: AsyncMock | None = None,
    organization_repo: AsyncMock | None = None,
    renderer: AsyncMock | None = None,
    extractor: AsyncMock | None = None,
    draft_generator: AsyncMock | None = None,
) -> TemplateAuthoringService:
    return TemplateAuthoringService(
        template_repo=template_repo or AsyncMock(),
        template_format_repo=template_format_repo or AsyncMock(),
        organization_repo=organization_repo or AsyncMock(),
        renderer=renderer or AsyncMock(),
        extractor=extractor or AsyncMock(),
        draft_generator=draft_generator or AsyncMock(),
    )


class TestGenerateDraftFromPrompt:
    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_warns_when_company_template_has_no_contract_date_mapping(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}",
                fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert document_type == DocumentType.COMPANY
        assert any("mapeo de vigencia del contrato" in warning for warning in draft.warnings)

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_injects_contract_date_clause_into_body(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}",
                fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
                contract_date_mapping={
                    "start_date_field": "fecha_inicio_contrato",
                    "end_date_field": "fecha_vencimiento",
                },
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert document_type == DocumentType.COMPANY
        assert draft.content.contract_date_mapping is not None
        assert "{{ fecha_inicio_contrato }}" in draft.content.body_md
        assert "{{ fecha_vencimiento }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == [
            "cliente_nombre",
            "fecha_inicio_contrato",
            "fecha_vencimiento",
        ]
        assert draft.content.operational_fields == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_strict_mode_rejects_missing_explicit_contract_dates(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}",
                fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
                contract_date_mapping={
                    "start_date_field": "fecha_inicio_contrato",
                    "end_date_field": "fecha_fin_contrato",
                },
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        with pytest.raises(ValueError, match="generation_mode='adaptive'"):
            await service.generate_draft_from_prompt(
                request=GenerateTemplateDraftRequest(
                    format_code="base_company",
                    generation_mode=TemplateGenerationMode.STRICT,
                ),
                organization_id=1,
                user_role=UserRole.MANAGER,
            )

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_converts_bracket_reference_markers_to_fields(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n[NÚMERO DE PARTIDA EMPRESA]\n[FECHA ACUERDO DIRECTORIO]\n[CIERRE DEL DOCUMENTO]",
                fields=[],
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert "{{ numero_partida_empresa }}" in draft.content.body_md
        assert "{{ fecha_acuerdo_directorio }}" in draft.content.body_md
        assert "[CIERRE DEL DOCUMENTO]" not in draft.content.body_md
        assert [field.key for field in draft.content.fields] == ["numero_partida_empresa", "fecha_acuerdo_directorio"]
        assert draft.content.fields[1].type == "date"
        assert draft.content.fields[0].placeholder == "Ej. 11012345"
        assert draft.content.fields[1].placeholder == "Ej. 2026-12-31"

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_keeps_manual_fields_as_detected(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ contratista_ruc }}\n{{ representante_nombre_contratista }}",
                fields=[
                    TemplateField(key="contratista_ruc", label="RUC del Contratista", required=True),
                    TemplateField(key="representante_nombre_contratista", label="Nombre del Representante del Contratista", required=True),
                ],
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert "{{ contratista_ruc }}" in draft.content.body_md
        assert "{{ representante_nombre_contratista }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == ["contratista_ruc", "representante_nombre_contratista"]

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_canonicalizes_employer_aliases_to_auto_variables(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ representante_nombre_empresa }}\n{{ representante_dni_empresa }}\n{{ empleador_tipo_sociedad }}",
                fields=[
                    TemplateField(key="representante_nombre_empresa", label="Nombre del Representante de La Empresa", required=True),
                    TemplateField(key="representante_dni_empresa", label="DNI del Representante de La Empresa", required=True),
                    TemplateField(key="empleador_tipo_sociedad", label="Tipo de Sociedad de la Empresa", required=True),
                ],
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert "{{ representante_nombre }}" in draft.content.body_md
        assert "{{ representante_dni }}" in draft.content.body_md
        assert "{{ empleador_descripcion }}" in draft.content.body_md
        assert draft.content.fields == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_discards_stale_ai_warnings_after_backend_sync(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ contrato_fecha_inicio }}\n{{ contrato_fecha_fin }}",
                fields=[
                    TemplateField(key="contrato_fecha_inicio", label="Fecha inicio", type="date", required=True),
                    TemplateField(key="contrato_fecha_fin", label="Fecha fin", type="date", required=True),
                ],
            ),
            warnings=[
                "La plantilla no define un mapeo de vigencia del contrato para fecha de inicio y fin.",
                "El campo 'empleador_email' no está siendo utilizado en el cuerpo del documento.",
            ],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert draft.content.contract_date_mapping is not None
        assert draft.warnings == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_forces_visible_placeholders_to_required(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ gerente_ruc }}\n{{ monto_retribucion_mensual }}",
                fields=[
                    TemplateField(key="gerente_ruc", label="RUC del Gerente", required=False),
                    TemplateField(key="monto_retribucion_mensual", label="Monto", type="number", required=False),
                ],
            ),
            warnings=[],
            source={},
        )
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert all(field.required for field in draft.content.fields)
        assert draft.content.fields[0].placeholder == "Ej. 20123456789"
        assert draft.content.fields[1].placeholder == "Ej. 1500"

    @pytest.mark.asyncio
    async def test_preview_template_includes_operational_fields_in_mock_payload(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        renderer = AsyncMock()
        renderer.render.return_value = "# Preview"
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            renderer=renderer,
        )

        response = await service.preview_template(
            request=PreviewTemplateRequest(
                format_code="base_company",
                content=TemplateContent(
                    body_md="# Contrato\n{{ cliente_nombre }}",
                    fields=[TemplateField(key="cliente_nombre", label="Cliente", type="text", required=True)],
                    operational_fields=[
                        TemplateField(key="start_date", label="Fecha inicio", type="date", required=True),
                        TemplateField(key="end_date", label="Fecha fin", type="date", required=True),
                    ],
                    contract_date_mapping={"start_date_field": "start_date", "end_date_field": "end_date"},
                ),
            ),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert response.resolved_payload["start_date"] == "2026-01-01"
        assert response.resolved_payload["end_date"] == "2026-01-01"
        assert 'data-generated-signatures="true"' in response.markdown


class TestPublishTemplate:
    @pytest.mark.asyncio
    async def test_publish_template_requires_contract_date_mapping_for_company_templates(self):
        template_repo = AsyncMock()
        template_repo.get_template_by_id.return_value = TemplateTable(
            id=1,
            organization_id=1,
            name="Plantilla Empresa",
            document_type=DocumentType.COMPANY,
            template_format_id=1,
            state=TemplateState.DRAFT,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}",
                fields=[TemplateField(key="cliente_nombre", label="Cliente", required=True)],
            ).model_dump(mode="python"),
        )
        template_format_repo = AsyncMock()
        template_format_repo.get_by_id.return_value = _make_format()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        service = _make_authoring_service(template_repo=template_repo, template_format_repo=template_format_repo)

        with pytest.raises(ValueError, match="mapeo de vigencia del contrato"):
            await service.publish_template(template_id=1, organization_id=1, user_role=UserRole.MANAGER)

        template_repo.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_template_persists_inferred_contract_date_mapping(self):
        template_repo = AsyncMock()

        async def _publish(entity: TemplateTable) -> TemplateTable:
            return entity

        template_repo.get_template_by_id.return_value = TemplateTable(
            id=1,
            organization_id=1,
            name="Plantilla Empresa",
            document_type=DocumentType.COMPANY,
            template_format_id=1,
            state=TemplateState.DRAFT,
            content=TemplateContent(
                body_md="# Contrato\n{{ vigencia_inicio_real }}\n{{ vigencia_fin_real }}",
                fields=[
                    TemplateField(key="vigencia_inicio_real", label="Inicio de vigencia", type="date", required=True),
                    TemplateField(key="vigencia_fin_real", label="Fin de vigencia", type="date", required=True),
                ],
            ).model_dump(mode="python"),
        )
        template_repo.publish.side_effect = _publish
        template_format_repo = AsyncMock()
        template_format_repo.get_by_id.return_value = _make_format()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        service = _make_authoring_service(template_repo=template_repo, template_format_repo=template_format_repo)

        response = await service.publish_template(template_id=1, organization_id=1, user_role=UserRole.MANAGER)

        assert response.content.contract_date_mapping is not None
        assert response.content.contract_date_mapping.start_date_field == "vigencia_inicio_real"
        assert response.content.contract_date_mapping.end_date_field == "vigencia_fin_real"
        assert response.content.operational_fields == []
