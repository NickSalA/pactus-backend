"""Módulo de enrutamiento para la API de plantillas."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from contractai_backend.modules.templates.domain.entities import TemplateTable

from ....shared.api.dependencies.security import CurrentUserDep
from ..application.services.template_authoring_service import TemplateAuthoringService
from ..application.services.template_service import TemplateService
from .dependencies import get_template_authoring_service, get_template_service
from .schemas import (
    CreateTemplateRequest,
    GenerateTemplateDraftRequest,
    PersistedTemplateDraftResponse,
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    TemplateResponse,
    UpdateTemplateRequest,
    build_template_response,
)

router = APIRouter()

TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
TemplateAuthoringServiceDep = Annotated[TemplateAuthoringService, Depends(get_template_authoring_service)]


def _build_default_file_request(filename: str) -> GenerateTemplateDraftRequest:
    """Construye un request minimo desde el nombre del archivo."""
    base_name = Path(filename).stem.replace("_", " ").strip() or "Plantilla sin nombre"
    return GenerateTemplateDraftRequest(
        name=base_name,
        description="Borrador generado desde archivo de referencia",
    )


def _parse_draft_request(raw_request: str | None) -> GenerateTemplateDraftRequest | None:
    """Parsea el JSON opcional del draft."""
    if raw_request is None:
        return None

    try:
        return GenerateTemplateDraftRequest(**json.loads(raw_request))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payload invalido: {e}") from e


@router.post(path="/{template_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_template(
    template_id: int,
    request: dict[str, Any],
    template_service: TemplateServiceDep,
    current_user: CurrentUserDep,
):
    """Endpoint para generar un documento a partir de una plantilla."""
    try:
        generated_document = await template_service.generate_contract(
            template_id=template_id, form_data=request, organization_id=current_user.organization_id
        )
        return generated_document
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al generar el documento: {e!s}") from e


@router.post(path="/drafts", response_model=PersistedTemplateDraftResponse, status_code=status.HTTP_201_CREATED)
async def generate_template_draft(
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile | None = None,
    request: str | None = Form(None),
) -> PersistedTemplateDraftResponse:
    """Endpoint para generar un borrador de plantilla desde request, archivo o ambos."""
    if file is None and request is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes enviar un archivo, un request o ambos.")

    try:
        request_obj = _parse_draft_request(request)

        if file is not None:
            if file.filename is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo invalido.")

            draft_request = request_obj or _build_default_file_request(file.filename)
            file_content = await file.read()
            return await template_service.generate_and_save_draft_from_file(
                request=draft_request,
                file_content=file_content,
                filename=file.filename,
                organization_id=current_user.organization_id,
            )

        if request_obj is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes enviar un request valido cuando no subas archivo.")

        return await template_service.generate_and_save_draft_from_prompt(
            request=request_obj,
            organization_id=current_user.organization_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al generar el borrador: {e!s}") from e


@router.post(path="/preview", response_model=PreviewTemplateResponse, status_code=status.HTTP_200_OK)
async def preview_template(
    request: PreviewTemplateRequest,
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
) -> PreviewTemplateResponse:
    """Endpoint para previsualizar una plantilla."""
    try:
        return await template_service.preview_template(
            request=request,
            organization_id=current_user.organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al previsualizar: {e!s}") from e


@router.get(path="/{template_id}", response_model=TemplateResponse, status_code=status.HTTP_200_OK)
async def get_template(
    template_id: int,
    template_service: TemplateServiceDep,
    current_user: CurrentUserDep,
) -> TemplateResponse:
    """Endpoint para obtener los detalles de una plantilla."""
    try:
        template: TemplateTable | None = await template_service.get_template(template_id=template_id, organization_id=current_user.organization_id)
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
        return build_template_response(template)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al obtener la plantilla: {e!s}") from e


@router.post(path="/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: CreateTemplateRequest,
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
) -> TemplateResponse:
    """Endpoint para crear una plantilla."""
    try:
        return await template_service.create_template(
            request=request,
            organization_id=current_user.organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al crear la plantilla: {e!s}") from e


@router.patch(path="/{template_id}", response_model=TemplateResponse, status_code=status.HTTP_200_OK)
async def update_template(
    template_id: int,
    request: UpdateTemplateRequest,
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
) -> TemplateResponse:
    """Endpoint para actualizar una plantilla en borrador."""
    try:
        return await template_service.update_template(
            template_id=template_id,
            request=request,
            organization_id=current_user.organization_id,
        )
    except ValueError as e:
        detail = str(e)
        status_code = status.HTTP_404_NOT_FOUND if detail == "Plantilla no encontrada" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al actualizar la plantilla: {e!s}") from e


@router.get(path="/", response_model=Sequence[TemplateResponse], status_code=status.HTTP_200_OK)
async def list_templates(
    template_service: TemplateServiceDep,
    current_user: CurrentUserDep,
) -> Sequence[TemplateResponse]:
    """Endpoint para listar las plantillas de la organización."""
    try:
        templates: Sequence[TemplateTable] = await template_service.list_templates(organization_id=current_user.organization_id)
        return [build_template_response(template) for template in templates]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al listar las plantillas: {e!s}") from e
