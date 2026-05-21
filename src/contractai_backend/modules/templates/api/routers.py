"""Módulo de enrutamiento para la API de plantillas."""

import json
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.templates.domain.value_objs import TemplateState

from ....shared.api.dependencies.security import CurrentUserDep
from ..application.services.template_authoring_service import TemplateAuthoringService
from ..application.services.template_service import TemplateService
from .dependencies import get_template_authoring_service, get_template_service
from .schemas import (
    CreateTemplateRequest,
    DocumentResponse,
    GenerateTemplateDraftRequest,
    PersistedTemplateDraftResponse,
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    TemplateFormatResponse,
    TemplateResponse,
    UpdateTemplateRequest,
)

router = APIRouter()

TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
TemplateAuthoringServiceDep = Annotated[TemplateAuthoringService, Depends(get_template_authoring_service)]


def _parse_draft_request(raw_request: str | None) -> GenerateTemplateDraftRequest | None:
    """Parsea el JSON opcional del draft."""
    if raw_request is None:
        return None

    try:
        return GenerateTemplateDraftRequest(**json.loads(raw_request))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payload invalido: {e}") from e


@router.post(path="/{template_id}/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_template(
    template_id: int,
    request: dict[str, Any],
    template_service: TemplateServiceDep,
    current_user: CurrentUserDep,
) -> DocumentResponse:
    """Endpoint para generar un documento a partir de una plantilla."""
    try:
        return await template_service.generate_contract(
            template_id=template_id,
            form_data=request,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al generar el documento: {e!s}") from e


@router.get(path="/formats", response_model=list[TemplateFormatResponse], status_code=status.HTTP_200_OK)
async def list_template_formats(
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
    document_type: DocumentType | None = None,
) -> list[TemplateFormatResponse]:
    """Endpoint para listar los formatos disponibles para el usuario."""
    try:
        formats = await template_service.list_available_formats(
            user_role=current_user.role,
            requested_document_type=document_type,
        )
        return [TemplateFormatResponse.model_validate(item, from_attributes=True) for item in formats]
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al listar formatos: {e!s}") from e


@router.post(path="/drafts", response_model=PersistedTemplateDraftResponse, status_code=status.HTTP_201_CREATED)
async def generate_template_draft(
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile | None = None,
    request: str = Form(...),
) -> PersistedTemplateDraftResponse:
    """Endpoint para generar un borrador de plantilla desde request, archivo o ambos."""
    try:
        request_obj = _parse_draft_request(request)
        if request_obj is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes enviar un request valido.")

        if file is not None:
            if file.filename is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archivo invalido.")

            file_content = await file.read()
            draft = await template_service.generate_and_save_draft_from_file(
                request=request_obj,
                file_content=file_content,
                filename=file.filename,
                organization_id=current_user.organization_id,
                user_role=current_user.role,
            )
            return PersistedTemplateDraftResponse.model_validate(draft, from_attributes=True)

        draft = await template_service.generate_and_save_draft_from_prompt(
            request=request_obj,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return PersistedTemplateDraftResponse.model_validate(draft, from_attributes=True)
    except HTTPException:
        raise
    except AppError:
        raise
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
        preview = await template_service.preview_template(
            request=request,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return PreviewTemplateResponse.model_validate(preview, from_attributes=True)
    except AppError:
        raise
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
        template = await template_service.get_template(
            template_id=template_id,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plantilla no encontrada")
        return TemplateResponse.model_validate(template, from_attributes=True)
    except HTTPException:
        raise
    except AppError:
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
        template = await template_service.create_template(
            request=request,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return TemplateResponse.model_validate(template, from_attributes=True)
    except AppError:
        raise
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
        template = await template_service.update_template(
            template_id=template_id,
            request=request,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return TemplateResponse.model_validate(template, from_attributes=True)
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al actualizar la plantilla: {e!s}") from e


@router.post(path="/{template_id}/publish", response_model=TemplateResponse, status_code=status.HTTP_200_OK)
async def publish_template(
    template_id: int,
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
) -> TemplateResponse:
    """Endpoint para publicar una plantilla en borrador."""
    try:
        template = await template_service.publish_template(
            template_id=template_id,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return TemplateResponse.model_validate(template, from_attributes=True)
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al publicar la plantilla: {e!s}") from e


@router.post(path="/{template_id}/archive", response_model=TemplateResponse, status_code=status.HTTP_200_OK)
async def archive_template(
    template_id: int,
    template_service: TemplateAuthoringServiceDep,
    current_user: CurrentUserDep,
) -> TemplateResponse:
    """Endpoint para archivar una plantilla."""
    try:
        template = await template_service.archive_template(
            template_id=template_id,
            organization_id=current_user.organization_id,
            user_role=current_user.role,
        )
        return TemplateResponse.model_validate(template, from_attributes=True)
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al archivar la plantilla: {e!s}") from e


@router.get(path="/", response_model=Sequence[TemplateResponse], status_code=status.HTTP_200_OK)
async def list_templates(
    template_service: TemplateServiceDep,
    current_user: CurrentUserDep,
    document_type: DocumentType | None = None,
    format_code: str | None = None,
    state: TemplateState | None = None,
) -> Sequence[TemplateResponse]:
    """Endpoint para listar las plantillas de la organización."""
    try:
        templates = await template_service.list_templates(
            organization_id=current_user.organization_id,
            user_role=current_user.role,
            document_type=document_type,
            format_code=format_code,
            state=state,
        )
        return [TemplateResponse.model_validate(template, from_attributes=True) for template in templates]
    except AppError:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al listar las plantillas: {e!s}") from e
