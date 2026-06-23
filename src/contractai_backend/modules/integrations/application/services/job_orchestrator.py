"""Application service for orchestrating background import jobs."""

from typing import Any

from loguru import logger

from contractai_backend.modules.integrations.domain.exceptions import InvalidCloudTokenError

from ...composition import build_background_integration_service
from ..jobs import FilePhase, JobTracker, job_registry


async def _process_single_file(
    tracker: JobTracker,
    token: dict,
    file_item: dict[str, Any],
    organization_id: int,
    imported_by_user_id: int | None,
    imported_by: dict[str, Any] | None = None,
) -> bool:
    file_id = str(file_item.get("file_id") or "").strip()
    if not file_id:
        logger.warning("Skipping file with empty file_id")
        return True

    try:
        await tracker.set_phase(file_id, FilePhase.DATABASE)
    except Exception as e:
        logger.error(f"Error updating phase to DATABASE for file {file_id}: {e}")

    try:
        async with build_background_integration_service() as service:
            await service.process_import(
                token=token,
                files=[file_item],
                organization_id=organization_id,
                imported_by_user_id=imported_by_user_id,
                imported_by=imported_by,
            )

        await tracker.set_phase(file_id, FilePhase.KNOWLEDGE_BASE)
        await tracker.set_phase(file_id, FilePhase.COMPLETED)
        return True

    except InvalidCloudTokenError as e:
        logger.error(f"Fallo de autenticación: {e}")
        await tracker.complete("FAILED")
        await job_registry.schedule_cleanup(tracker)
        return False

    except Exception as e:
        logger.error(f"Error processing file {file_id}: {e}")
        try:
            await tracker.set_phase(file_id, FilePhase.FAILED, error="Error al procesar el archivo")
        except Exception as update_error:
            logger.error(f"Error updating phase to FAILED for file {file_id}: {update_error}")
        return True


async def process_drive_import_in_background(
    job_id: str,
    token: dict,
    files: list[dict[str, Any]],
    organization_id: int,
    imported_by_user_id: int | None = None,
    imported_by: dict[str, Any] | None = None,
) -> None:
    tracker = job_registry.get(job_id)
    if not tracker:
        logger.error(f"Job {job_id} not found in tracker")
        return

    for file_item in files:
        should_continue = await _process_single_file(
            tracker=tracker,
            token=token,
            file_item=file_item,
            organization_id=organization_id,
            imported_by_user_id=imported_by_user_id,
            imported_by=imported_by,
        )
        if not should_continue:
            return

    await tracker.complete("COMPLETED")
    await job_registry.schedule_cleanup(tracker)
