"""Server-Sent Events (SSE) generator for integration imports."""

import asyncio

from loguru import logger

from ..application.jobs import JobTracker
from .schemas import ImportEvent

PING_TIMEOUT = 30


async def generate_import_sse_events(tracker: JobTracker):
    """Generates SSE events from the job tracker event queue."""
    initial_event = ImportEvent(
        type="initial_state",
        job_id=tracker.job_id,
        status=tracker.status,
        files=list(tracker.files.values()),
    )
    yield f"event: {initial_event.type}\ndata: {initial_event.model_dump_json(exclude={'type'})}\n\n"

    while True:
        try:
            job_event = await asyncio.wait_for(tracker.event_queue.get(), timeout=PING_TIMEOUT)
            event = ImportEvent(
                type=job_event.type,
                job_id=job_event.job_id,
                status=job_event.status,
                files=job_event.files,
                error=job_event.error,
            )
            yield f"event: {event.type}\ndata: {event.model_dump_json(exclude={'type'})}\n\n"
            if event.type == "job_complete":
                break
        except asyncio.TimeoutError:  # noqa: UP041
            yield "event: ping\ndata: null\n\n"
        except Exception as exc:
            logger.error(f"Error in SSE generator: {exc}")
            break
