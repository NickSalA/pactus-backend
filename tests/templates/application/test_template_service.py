"""Tests for TemplateService labor contract naming."""

from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.templates.application.services.template_service import TemplateService
from contractai_backend.modules.templates.domain.entities import TemplateTable
from contractai_backend.modules.templates.domain.value_objs import TemplateState


def _make_template() -> TemplateTable:
    return TemplateTable(
        organization_id=1,
        name="Plantilla Laboral",
        content={"body_md": "# Hola {{trabajador_nombre}}", "fields": [], "version": "1.0"},
        state=TemplateState.PUBLISHED,
    )


@pytest.mark.asyncio
async def test_generate_contract_uses_standard_worker_contract_name() -> None:
    template_repo = AsyncMock()
    template_repo.get_template_by_id.return_value = _make_template()

    organization_repo = AsyncMock()
    organization_repo.get_organization_data.return_value = {}

    renderer = AsyncMock()
    renderer.render.return_value = "# Contrato"

    document_generator = AsyncMock()
    document_generator.generate_pdf.return_value = b"pdf"

    document_adapter = AsyncMock()
    document_adapter.save_generated_document.return_value = {"id": 1}

    service = TemplateService(
        template_repo=template_repo,
        organization_repo=organization_repo,
        renderer=renderer,
        document_generator=document_generator,
        document_adapter=document_adapter,
    )

    await service.generate_contract(
        template_id=1,
        organization_id=1,
        form_data={"trabajador_nombre": "Ana Perez"},
    )

    payload = document_adapter.save_generated_document.await_args.kwargs["document_payload"]
    assert payload["name"] == "Contrato Estándar de Trabajador - Ana Perez"
    assert payload["client"] == "Ana Perez"
    assert payload["type"] == "LABOR"
