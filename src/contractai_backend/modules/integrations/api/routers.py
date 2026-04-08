from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from contractai_backend.modules.documents.domain.access_policy import can_write_document_type
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.shared.config import settings
from contractai_backend.shared.api.dependencies.security import CurrentUserDep
from .dependencies import get_integration_service, process_drive_import_in_background
from .schemas import AuthURLResponse, DriveRequest, ImportRequest, ImportResponse, TokenResponse

router = APIRouter(prefix="/drive", tags=["Integrations"])
IntegrationServiceDep = Annotated[IntegrationService, Depends(get_integration_service)]


@router.get("/auth-url", response_model=AuthURLResponse)
async def get_authorization_url(service: IntegrationServiceDep):
    url = service.get_authorization_url()
    return AuthURLResponse(url=url)


@router.get("/callback", response_model=TokenResponse)
async def oauth_callback(code: str, service: IntegrationServiceDep):
    token_data = await service.authenticate(code=code)
    return TokenResponse(**token_data)


@router.post("/download/{file_id}")
async def download_drive_file(file_id: str, request: DriveRequest, service: IntegrationServiceDep, _: CurrentUserDep):
    file_bytes = await service.retrieve_file(token=request.token, file_id=file_id)
    return Response(content=file_bytes, media_type="application/octet-stream")


@router.post("/import", response_model=ImportResponse)
async def import_drive_files(request: ImportRequest, background_tasks: BackgroundTasks, current_user: CurrentUserDep):
    if any(not can_write_document_type(current_user.role, file_item.document.type) for file_item in request.files):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para importar este tipo de contrato",
        )

    files_payload = [file_item.model_dump(mode="python") for file_item in request.files]
    background_tasks.add_task(process_drive_import_in_background, request.token, files_payload, current_user.organization_id, current_user.id)
    return ImportResponse(
        message="La importación ha comenzado en segundo plano.",
        queued_files=len(request.files),
        index_name=settings.DRIVE_INDEX_NAME,
    )
