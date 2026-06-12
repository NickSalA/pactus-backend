"""HTTP endpoints for third-party integrations."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from contractai_backend.modules.documents.domain.access_policy import can_write_document_type
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.shared.api.dependencies.security import CurrentUserDep
from contractai_backend.shared.config import settings

from .dependencies import (
    create_job,
    generate_import_sse_events,
    get_integration_service,
    get_job,
    get_user_active_job,
    process_drive_import_in_background,
)
from .schemas import AuthURLResponse, DriveRequest, ImportRequest, ImportResponse, TokenResponse

router = APIRouter(prefix="/drive")
IntegrationServiceDep = Annotated[IntegrationService, Depends(get_integration_service)]


@router.get("/auth-url", response_model=AuthURLResponse)
async def get_authorization_url(service: IntegrationServiceDep):
    """Returns a Google Drive OAuth authorization URL."""
    url = service.get_authorization_url()
    return AuthURLResponse(url=url)


@router.get("/callback", response_model=TokenResponse)
async def oauth_callback(code: str, service: IntegrationServiceDep):
    """Exchanges an OAuth authorization code for token data."""
    token_data = await service.authenticate(code=code)
    return TokenResponse(**token_data)


@router.post("/download/{file_id}")
async def download_drive_file(file_id: str, request: DriveRequest, service: IntegrationServiceDep, _: CurrentUserDep):
    """Downloads one Google Drive file through the configured provider."""
    file_bytes = await service.retrieve_file(token=request.token, file_id=file_id)
    return Response(content=file_bytes, media_type="application/octet-stream")


@router.post("/import", response_model=ImportResponse)
async def import_drive_files(request: ImportRequest, background_tasks: BackgroundTasks, current_user: CurrentUserDep):
    """Queues Google Drive files for document ingestion."""
    user_role = getattr(current_user, "role", None)
    if any(
        file_item.document.contract_type is not None and not can_write_document_type(user_role, file_item.document.contract_type)
        for file_item in request.files
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para importar este tipo de contrato",
        )

    active_job = get_user_active_job(current_user.id)
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una importación en progreso. Espere a que termine.",
        )

    files_payload = [file_item.model_dump(mode="python", exclude_unset=True, exclude_none=True) for file_item in request.files]
    tracker = create_job(files_payload, current_user.organization_id, current_user.id)

    imported_by = {
        "id": current_user.id,
        "organization_id": current_user.organization_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": str(current_user.role) if current_user.role else None,
        "is_active": current_user.is_active,
    }

    background_tasks.add_task(
        process_drive_import_in_background,
        tracker.job_id,
        request.token,
        files_payload,
        current_user.organization_id,
        current_user.id,
        imported_by,
    )

    return ImportResponse(
        message="La importación ha comenzado en segundo plano.",
        queued_files=len(request.files),
        index_name=settings.DRIVE_INDEX_NAME,
        job_id=tracker.job_id,
    )


@router.get("/import/{job_id}/events")
async def stream_import_events(job_id: str, current_user: CurrentUserDep):
    """SSE endpoint for tracking import progress."""
    tracker = get_job(job_id)
    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trabajo no encontrado.",
        )

    if tracker.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este trabajo.",
        )

    return StreamingResponse(
        generate_import_sse_events(tracker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
