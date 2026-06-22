"""HTTP endpoints for third-party integrations."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi.responses import StreamingResponse

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.documents.domain.access_policy import can_write_document_type
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.shared.api.dependencies.security import CurrentUserDep
from contractai_backend.shared.config import settings

from ..application.jobs import create_job, get_job, get_user_active_job
from ..application.services.job_orchestrator import process_drive_import_in_background
from ..domain.exceptions import DuplicateJobError, JobAccessDeniedError, JobNotFoundError
from .dependencies import get_integration_service
from .schemas import AuthURLResponse, DriveRequest, ImportRequest, ImportResponse, TokenResponse
from .sse import generate_import_sse_events

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
        raise ForbiddenError("No tiene permisos para importar este tipo de contrato")

    if get_user_active_job(current_user.id):
        raise DuplicateJobError()

    files_payload = [file_item.model_dump(mode="python", exclude_unset=True, exclude_none=True) for file_item in request.files]

    imported_by: dict[str, Any] = {
        "id": current_user.id,
        "organization_id": current_user.organization_id,
        "email": current_user.email,
        "full_name": getattr(current_user, "full_name", None),
        "role": str(current_user.role) if current_user.role else None,
        "is_active": True,
    }
    tracker = create_job(files_payload, current_user.organization_id, current_user.id)

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
        raise JobNotFoundError()

    if tracker.user_id != current_user.id:
        raise JobAccessDeniedError()

    return StreamingResponse(
        generate_import_sse_events(tracker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
