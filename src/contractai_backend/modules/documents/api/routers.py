"""Module containing API routers for document-related endpoints."""

import json
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile, status
from pydantic import ValidationError

from ....shared.api.dependencies.security import CurrentUserDep
from ...catalog.application.services import ServiceCatalogService
from ...users.domain.value_objs import UserRole
from ..application.services import DocumentCommandService, DocumentQueryService
from ..domain.exceptions import DocumentNotFoundError, DocumentValidationError, InvalidDocumentFileError
from .dependencies import get_document_command_service, get_document_query_service, get_service_catalog_service
from .schemas import (
    CreateDocumentDraftRequest,
    DocumentCatalogServiceResponse,
    DocumentFileUrlResponse,
    DocumentResponse,
    FileRequest,
    UpdateDocumentRequest,
)

router = APIRouter()


@router.get(path="/services", response_model=Sequence[DocumentCatalogServiceResponse], include_in_schema=False)
async def list_document_services_compat(
    service: Annotated[ServiceCatalogService, Depends(get_service_catalog_service)],
    current_user: CurrentUserDep,
    include_inactive: bool = Query(default=False),
) -> Sequence[DocumentCatalogServiceResponse]:
    """Backward-compatible alias for legacy /documents/services consumers."""
    user_role = getattr(current_user, "role", None)
    services = await service.list_services(
        organization_id=current_user.organization_id,
        include_inactive=include_inactive and user_role == UserRole.ADMIN,
    )
    return [DocumentCatalogServiceResponse(id=item.id, name=item.name) for item in services if item.id is not None]


@router.post(path="/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    file: UploadFile,
    service: Annotated[DocumentCommandService, Depends(get_document_command_service)],
    current_user: CurrentUserDep,
    document: str = Form("{}"),
) -> DocumentResponse:
    """Endpoint to create a new document."""
    try:
        doc_data = json.loads(document)
        doc_obj = CreateDocumentDraftRequest(**doc_data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise DocumentValidationError(f"Datos del documento invalidos: {e}") from e

    if file.filename is None or file.content_type is None:
        raise InvalidDocumentFileError()

    file_content: bytes = await file.read()
    file_data = FileRequest(content=file_content, filename=file.filename, content_type=file.content_type)
    user_role = getattr(current_user, "role", None)

    saved_document = await service.create_document(
        data=doc_obj,
        file_data=file_data,
        organization_id=current_user.organization_id,
        user_role=user_role,
    )
    return DocumentResponse.model_validate(saved_document)


@router.get(path="/", response_model=Sequence[DocumentResponse])
async def list_documents(
    service: Annotated[DocumentQueryService, Depends(get_document_query_service)],
    current_user: CurrentUserDep,
    limit: int | None = Query(default=None, ge=1, description="Maximum number of documents to return"),
    offset: int | None = Query(default=None, ge=0, description="Number of documents to skip"),
) -> Sequence[DocumentResponse]:
    """Endpoint to list documents with optional filters and pagination."""
    user_role = getattr(current_user, "role", None)
    documents = await service.get_documents(
        organization_id=current_user.organization_id,
        user_role=user_role,
        limit=limit,
        offset=offset,
    )
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get(path="/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    service: Annotated[DocumentQueryService, Depends(get_document_query_service)],
    current_user: CurrentUserDep,
) -> DocumentResponse:
    """Endpoint to retrieve a document by its ID."""
    user_role = getattr(current_user, "role", None)
    doc = await service.get_document(
        id=document_id,
        organization_id=current_user.organization_id,
        user_role=user_role,
    )
    if not doc:
        raise DocumentNotFoundError(document_id=document_id)
    return DocumentResponse.model_validate(doc)


@router.get(path="/{document_id}/file-url", response_model=DocumentFileUrlResponse)
async def get_document_file_url(
    document_id: int,
    service: Annotated[DocumentCommandService, Depends(get_document_command_service)],
    current_user: CurrentUserDep,
) -> DocumentFileUrlResponse:
    """Endpoint to generate a signed URL for a stored document file."""
    user_role = getattr(current_user, "role", None)
    url = await service.get_document_signed_url(
        id=document_id,
        organization_id=current_user.organization_id,
        user_role=user_role,
    )
    return DocumentFileUrlResponse(url=url)


@router.patch(path="/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    service: Annotated[DocumentCommandService, Depends(get_document_command_service)],
    current_user: CurrentUserDep,
    document: str = Form(...),
    file: UploadFile | None = None,
) -> DocumentResponse:
    """Endpoint to update an existing document."""
    try:
        doc_data = json.loads(document)
        doc_obj = UpdateDocumentRequest(**doc_data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise DocumentValidationError(f"Datos del documento invalidos: {e}") from e

    file_data = None
    if file:
        file_content: bytes = await file.read()
        if file.filename is None or file.content_type is None:
            raise InvalidDocumentFileError()
        file_data = FileRequest(content=file_content, filename=file.filename, content_type=file.content_type)

    user_role = getattr(current_user, "role", None)

    updated_doc = await service.update_document(
        id=document_id,
        data=doc_obj,
        organization_id=current_user.organization_id,
        user_role=user_role,
        file_data=file_data,
    )
    return DocumentResponse.model_validate(updated_doc)


@router.delete(path="/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_document(
    document_id: int,
    service: Annotated[DocumentCommandService, Depends(get_document_command_service)],
    current_user: CurrentUserDep,
) -> None:
    """Endpoint to delete a document by its ID."""
    user_role = getattr(current_user, "role", None)
    await service.delete_document(id=document_id, organization_id=current_user.organization_id, user_role=user_role)
