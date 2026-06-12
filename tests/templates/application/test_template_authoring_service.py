"""Tests unitarios para TemplateAuthoringService."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.templates.api.schemas import GenerateTemplateDraftRequest, PreviewTemplateRequest, TemplateDraftResponse
from contractai_backend.modules.templates.application.services.template_authoring_service import TemplateAuthoringService
from contractai_backend.modules.templates.domain.entities import TemplateContent, TemplateField, TemplateFormatTable, TemplateTable
from contractai_backend.modules.templates.domain.value_objs import TemplateGenerationMode, TemplateState
from contractai_backend.modules.templates.domain.exceptions import TemplateValidationError
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.modules.templates.application.services.template_draft_service import TemplateDraftService
from contractai_backend.modules.templates.application.services.template_reference_service import TemplateReferenceService


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
    activity_service: AsyncMock | None = None,
) -> TemplateAuthoringService:
    org_repo = organization_repo or AsyncMock()
    d_generator = draft_generator or AsyncMock()
    draft_service = TemplateDraftService(
        draft_generator=d_generator,
        organization_repo=org_repo,
    )
    reference_service = TemplateReferenceService()
    return TemplateAuthoringService(
        template_repo=template_repo or AsyncMock(),
        template_format_repo=template_format_repo or AsyncMock(),
        organization_repo=org_repo,
        renderer=renderer or AsyncMock(),
        extractor=extractor or AsyncMock(),
        activity_service=activity_service or AsyncMock(),
        draft_service=draft_service,
        reference_service=reference_service,
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
    async def test_generate_draft_from_prompt_preserves_clear_contract_date_fields_even_if_body_omits_them(self):
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
                fields=[
                    TemplateField(key="cliente_nombre", label="Cliente", required=True),
                    TemplateField(key="contrato_fecha_inicio", label="Fecha de Inicio del Contrato", type="date", required=True),
                    TemplateField(key="contrato_fecha_fin", label="Fecha de Fin del Contrato", type="date", required=True),
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert document_type == DocumentType.COMPANY
        assert draft.content.contract_date_mapping is not None
        assert draft.content.contract_date_mapping.start_date_field == "contrato_fecha_inicio"
        assert draft.content.contract_date_mapping.end_date_field == "contrato_fecha_fin"
        assert "{{ contrato_fecha_inicio }}" in draft.content.body_md
        assert "{{ contrato_fecha_fin }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == [
            "cliente_nombre",
            "contrato_fecha_inicio",
            "contrato_fecha_fin",
        ]
        assert draft.content.operational_fields == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_normalizes_legacy_date_filters(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ fecha_inicio_contrato | date: '%d/%m/%Y' }}\n{{ fecha_fin_contrato | date('%d/%m/%Y') }}",
                fields=[
                    TemplateField(key="fecha_inicio_contrato", label="Fecha de Inicio", type="date", required=True),
                    TemplateField(key="fecha_fin_contrato", label="Fecha de Fin", type="date", required=True),
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

        assert "| date:" not in draft.content.body_md
        assert "| date(" not in draft.content.body_md
        assert "{{ fecha_inicio_contrato | format_date('%d/%m/%Y') }}" in draft.content.body_md
        assert "{{ fecha_fin_contrato | format_date('%d/%m/%Y') }}" in draft.content.body_md

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_normalizes_day_month_year_filters(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md=(
                    "# Contrato\n"
                    "{{ fecha_inicio_contrato | day }}/{{ fecha_inicio_contrato | month }}/{{ fecha_inicio_contrato | year }}\n"
                    "{{ fecha_fin_contrato | day }}/{{ fecha_fin_contrato | month }}/{{ fecha_fin_contrato | year }}"
                ),
                fields=[
                    TemplateField(key="fecha_inicio_contrato", label="Fecha de Inicio", type="date", required=True),
                    TemplateField(key="fecha_fin_contrato", label="Fecha de Fin", type="date", required=True),
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

        assert "| day" not in draft.content.body_md
        assert "| month" not in draft.content.body_md
        assert "| year" not in draft.content.body_md
        assert "{{ fecha_inicio_contrato | format_date('%d') }}" in draft.content.body_md
        assert "{{ fecha_inicio_contrato | format_date('%m') }}" in draft.content.body_md
        assert "{{ fecha_inicio_contrato | format_date('%Y') }}" in draft.content.body_md

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_retries_after_invalid_jinja_output(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.side_effect = [
            TemplateDraftResponse(
                name="Plantilla Empresa",
                description=None,
                content=TemplateContent(
                    body_md="# Contrato\n{{ fecha_inicio_contrato | unsupported_filter('%d/%m/%Y') }}",
                    fields=[TemplateField(key="fecha_inicio_contrato", label="Fecha de Inicio", type="date", required=True)],
                ),
                warnings=[],
                source={},
            ),
            TemplateDraftResponse(
                name="Plantilla Empresa",
                description=None,
                content=TemplateContent(
                    body_md="# Contrato\n{{ fecha_inicio_contrato }}",
                    fields=[TemplateField(key="fecha_inicio_contrato", label="Fecha de Inicio", type="date", required=True)],
                ),
                warnings=[],
                source={},
            ),
        ]
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

        assert "unsupported_filter" not in draft.content.body_md
        assert draft.source["retries_used"] == 1
        assert draft_generator.generate.await_count == 2
        second_call = draft_generator.generate.await_args_list[1]
        assert second_call.kwargs["validation_feedback"] == [
            "Expresiones Jinja no soportadas: fecha_inicio_contrato | unsupported_filter('%d/%m/%Y')"
        ]

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_retries_after_raw_field_semantic_issues(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.side_effect = [
            TemplateDraftResponse(
                name="Plantilla Laboral",
                description=None,
                content=TemplateContent(
                    body_md="# Contrato\n{{ monto_remuneracion_literal }}\n{{ trabajador_dni }}",
                    fields=[
                        TemplateField(key="monto_remuneracion_literal", label="Monto de la Remuneración (en letras)", type="text", required=True),
                        TemplateField(key="trabajador_dni", label="DNI del Trabajador", type="text", required=True),
                    ],
                ),
                warnings=[],
                source={
                    "field_issues": [
                        "El campo 'monto_remuneracion_literal' debe usar type='text' porque representa un valor en letras.",
                        "El campo 'trabajador_dni' debe usar un placeholder de ejemplo con 'Ej.' y no texto instruccional.",
                    ]
                },
            ),
            TemplateDraftResponse(
                name="Plantilla Laboral",
                description=None,
                content=TemplateContent(
                    body_md="# Contrato\n{{ monto_remuneracion_literal }}\n{{ trabajador_dni }}",
                    fields=[
                        TemplateField(
                            key="monto_remuneracion_literal",
                            label="Monto de la Remuneración (en letras)",
                            type="text",
                            placeholder="Ej. mil quinientos",
                            required=True,
                        ),
                        TemplateField(key="trabajador_dni", label="DNI del Trabajador", type="text", placeholder="Ej. 12345678", required=True),
                    ],
                ),
                warnings=[],
                source={},
            ),
        ]
        service = _make_authoring_service(
            template_format_repo=template_format_repo,
            organization_repo=organization_repo,
            draft_generator=draft_generator,
        )

        draft, _ = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_labor", document_type=DocumentType.LABOR),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert draft.source["retries_used"] == 1
        assert "field_issues" not in draft.source
        second_call = draft_generator.generate.await_args_list[1]
        assert second_call.kwargs["validation_feedback"] == [
            "El campo 'monto_remuneracion_literal' debe usar type='text' porque representa un valor en letras.",
            "El campo 'trabajador_dni' debe usar un placeholder de ejemplo con 'Ej.' y no texto instruccional.",
        ]

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

        with pytest.raises(TemplateValidationError, match="generation_mode='adaptive'"):
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
        assert draft.content.fields[0].type == "number"
        assert draft.content.fields[1].type == "date"
        assert draft.content.fields[0].placeholder == "Ej. 1000"
        assert draft.content.fields[1].placeholder == "Ej. 2026-12-31"
    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_removes_reference_image_artifacts(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Laboral",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\nFirmado en {{ lugar_firma }}.\n\n!{{ firma_empleador_trabajador_con_marca_agua_prodlab }}(page_2_image_1_v2.jpg)",
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_labor", document_type=DocumentType.LABOR),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert document_type == DocumentType.LABOR
        assert "firma_empleador_trabajador_con_marca_agua_prodlab" not in draft.content.body_md
        assert "page_2_image_1_v2.jpg" not in draft.content.body_md

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_removes_trailing_signature_block_placeholders(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md=(
                    "# Contrato\n"
                    "{{ cliente_nombre }}\n\n"
                    "_________________________\n"
                    "LA EMPRESA\n"
                    "{{ representante_nombre }}\n\n"
                    "_________________________\n"
                    "EL GERENTE\n"
                    "{{ gerente_representante_nombre }}"
                ),
                fields=[
                    TemplateField(key="cliente_nombre", label="Cliente", required=True),
                    TemplateField(key="representante_nombre", label="Representante Legal", required=True),
                    TemplateField(key="gerente_representante_nombre", label="Representante del Gerente", required=True),
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert document_type == DocumentType.COMPANY
        assert draft.content.body_md == "# Contrato\n{{ cliente_nombre }}"
        assert [field.key for field in draft.content.fields] == ["cliente_nombre"]
        assert draft.content.operational_fields == []

    @pytest.mark.asyncio

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
    async def test_generate_draft_from_prompt_drops_organization_auto_variables_from_operational_fields(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Laboral",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ empleador_razon_social }}\n{{ trabajador_nombre }}",
                fields=[TemplateField(key="trabajador_nombre", label="Nombre del Trabajador", required=True)],
                operational_fields=[
                    TemplateField(key="empleador_razon_social", label="Razón Social del Empleador", required=False),
                    TemplateField(key="empleador_domicilio", label="Domicilio del Empleador", required=False),
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_labor", document_type=DocumentType.LABOR),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert document_type == DocumentType.LABOR
        assert "{{ empleador_razon_social }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == ["trabajador_nombre"]
        assert draft.content.operational_fields == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_drops_organization_auto_variable_aliases_from_operational_fields(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Laboral",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ empresa_razon_social }}\n{{ trabajador_nombre }}",
                fields=[TemplateField(key="trabajador_nombre", label="Nombre del Trabajador", required=True)],
                operational_fields=[
                    TemplateField(key="empresa_ruc", label="RUC de la Empresa", required=False),
                    TemplateField(key="empresa_razon_social", label="Razón social de la Empresa", required=False),
                    TemplateField(key="empresa_domicilio", label="Domicilio de la Empresa", required=False),
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_labor", document_type=DocumentType.LABOR),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert document_type == DocumentType.LABOR
        assert "{{ empleador_razon_social }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == ["trabajador_nombre"]
        assert draft.content.operational_fields == []

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_resolves_duplicate_keys_across_visible_and_operational_groups(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format()
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Empresa",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ cliente_nombre }}\n{{ representante_cargo }}",
                fields=[
                    TemplateField(key="cliente_nombre", label="Cliente", required=True),
                    TemplateField(key="representante_cargo", label="Cargo del Representante", required=True),
                    TemplateField(key="contratista_ruc", label="RUC del Contratista", required=True),
                ],
                operational_fields=[
                    TemplateField(key="representante_cargo", label="Cargo del Representante", required=False),
                    TemplateField(key="contratista_ruc", label="RUC del Contratista", required=False),
                    TemplateField(key="contratista_objeto_social", label="Objeto Social del Contratista", required=False),
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_company"),
            organization_id=1,
            user_role=UserRole.MANAGER,
        )

        assert document_type == DocumentType.COMPANY
        assert [field.key for field in draft.content.fields] == ["cliente_nombre", "representante_cargo"]
        assert [field.key for field in draft.content.operational_fields] == ["contratista_ruc", "contratista_objeto_social"]

    @pytest.mark.asyncio
    async def test_generate_draft_from_prompt_normalizes_supported_manual_field_aliases(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
        organization_repo = AsyncMock()
        organization_repo.get_organization_data.return_value = {}
        draft_generator = AsyncMock()
        draft_generator.generate.return_value = TemplateDraftResponse(
            name="Plantilla Laboral",
            description=None,
            content=TemplateContent(
                body_md="# Contrato\n{{ remuneracion_mensual_fija }}",
                fields=[
                    TemplateField(
                        key="remuneracion_mensual_fija",
                        label="Remuneración Mensual Fija",
                        type="number",
                        required=True,
                    )
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

        draft, document_type = await service.generate_draft_from_prompt(
            request=GenerateTemplateDraftRequest(format_code="base_labor", document_type=DocumentType.LABOR),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert document_type == DocumentType.LABOR
        assert "{{ remuneracion_mensual }}" in draft.content.body_md
        assert [field.key for field in draft.content.fields] == ["remuneracion_mensual"]
        assert draft.content.fields[0].placeholder == "Ej. 1000"

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
        assert draft.content.fields[1].placeholder == "Ej. 1000"

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

    @pytest.mark.asyncio
    async def test_preview_template_uses_time_mock_value_for_time_fields(self):
        template_format_repo = AsyncMock()
        template_format_repo.get_by_document_type_and_code.return_value = _make_format(document_type=DocumentType.LABOR)
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
                format_code="base_labor",
                document_type=DocumentType.LABOR,
                content=TemplateContent(
                    body_md="# Jornada\n{{ hora_ingreso }}",
                    fields=[TemplateField(key="hora_ingreso", label="Hora de ingreso", type="time", required=True)],
                ),
            ),
            organization_id=1,
            user_role=UserRole.ADMIN,
        )

        assert response.resolved_payload["hora_ingreso"] == "09:00"


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

        with pytest.raises(TemplateValidationError, match="mapeo de vigencia del contrato"):
            await service.publish_template(
                template_id=1,
                actor=UserTable(id=1, organization_id=1, role=UserRole.MANAGER, email="a@b.com", password_hash=""),
            )

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

        response = await service.publish_template(
            template_id=1,
            actor=UserTable(id=1, organization_id=1, role=UserRole.MANAGER, email="a@b.com", password_hash=""),
        )

        assert response.content.contract_date_mapping is not None
        assert response.content.contract_date_mapping.start_date_field == "vigencia_inicio_real"
        assert response.content.contract_date_mapping.end_date_field == "vigencia_fin_real"
        assert response.content.operational_fields == []


class TestReferenceDocumentClassifier:
    def test_classifies_labor_reference_with_employer_and_worker_terms(self):
        service = TemplateReferenceService()

        detected_type = service.classify_reference_document_type(
            """
            MODELO DE CONTRATO DE TRABAJO SUJETO A MODALIDAD
            Conste por el presente documento el contrato de trabajo sujeto a modalidad.
            EL EMPLEADOR, con R.U.C. N° 12345678901, contrata a EL TRABAJADOR.
            Al amparo del Decreto Legislativo 728 y la Ley de Productividad y Competitividad Laboral.
            """
        )

        assert detected_type == DocumentType.LABOR

    def test_classifies_company_reference_with_management_terms(self):
        service = TemplateReferenceService()

        detected_type = service.classify_reference_document_type(
            """
            CONTRATO DE MANAGEMENT
            Celebran de una parte la EMPRESA y de otra parte el GERENTE.
            La persona juridica prestara servicios de gerenciamiento comercial.
            """
        )

        assert detected_type == DocumentType.COMPANY


class TestTemplateFieldTypeInference:
    def test_infers_correct_type_for_currency_and_amount_fields(self):
        from contractai_backend.modules.templates.application.services.template_content_synchronizer import TemplateContentSynchronizer

        synchronizer = TemplateContentSynchronizer()

        # Currency name / type fields should be 'text'
        assert synchronizer._infer_field_type(key="moneda", label="Moneda de pago", placeholder=None) == "text"
        assert synchronizer._infer_field_type(key="tipo_moneda", label="Tipo de moneda", placeholder=None) == "text"
        assert synchronizer._infer_field_type(key="moneda_pago", label="Moneda", placeholder=None) == "text"

        # Monetary amount fields should be 'number'
        assert synchronizer._infer_field_type(key="monto_moneda", label="Monto de la moneda", placeholder=None) == "number"
        assert synchronizer._infer_field_type(key="valor_moneda", label="Valor en moneda", placeholder=None) == "number"
        assert synchronizer._infer_field_type(key="retribucion_mensual", label="Monto retribución", placeholder=None) == "number"

        # Identifiers should be 'text'
        assert synchronizer._infer_field_type(key="representante_cliente_dni", label="DNI", placeholder=None) == "text"
        assert synchronizer._infer_field_type(key="ruc_empresa", label="RUC", placeholder=None) == "text"
        assert synchronizer._infer_field_type(key="telefono_contacto", label="Telefono", placeholder=None) == "text"

        # Explicit checks for user-provided examples
        assert synchronizer._infer_field_type(key="monto_retribucion", label="Monto de la retribución mensual (numérico)", placeholder=None) == "number"
        assert synchronizer._infer_field_type(key="monto_retribucion_literal", label="Monto de la retribución mensual (en letras)", placeholder=None) == "text"
