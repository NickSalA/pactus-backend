"""Job tracking and registry for background integration tasks."""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel


class FilePhase(StrEnum):
    PENDING = "PENDING"
    DATABASE = "DATABASE"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileStatus(BaseModel):
    file_id: str
    phase: FilePhase = FilePhase.PENDING
    error: str | None = None

@dataclass
class JobEvent:
    type: Literal["initial_state", "file_update", "job_complete"]
    job_id: str
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    files: list[FileStatus]
    error: str | None = None


@dataclass
class JobTracker:
    job_id: str
    organization_id: int
    user_id: int
    status: Literal["RUNNING", "COMPLETED", "FAILED"] = "RUNNING"
    files: dict[str, FileStatus] = field(default_factory=dict)
    event_queue: asyncio.Queue[JobEvent] = field(default_factory=asyncio.Queue)
    _cleanup_task: asyncio.Task | None = None

    async def set_phase(self, file_id: str, phase: FilePhase, error: str | None = None) -> None:
        file_status = self.files.get(file_id)
        if not file_status:
            return
        file_status.phase = phase
        file_status.error = error
        await self.event_queue.put(
            JobEvent(
                type="file_update",
                job_id=self.job_id,
                status=self.status,
                files=list(self.files.values()),
            )
        )

    async def complete(self, status: Literal["COMPLETED", "FAILED"]) -> None:
        self.status = status
        await self.event_queue.put(
            JobEvent(
                type="job_complete",
                job_id=self.job_id,
                status=status,
                files=list(self.files.values()),
            )
        )


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobTracker] = {}
        self._user_jobs: dict[int, str] = {}

    def create(self, files: list[dict[str, Any]], organization_id: int, user_id: int) -> JobTracker:
        job_id = str(uuid4())
        tracker = JobTracker(
            job_id=job_id,
            organization_id=organization_id,
            user_id=user_id,
            files={f["file_id"]: FileStatus(file_id=f["file_id"], phase=FilePhase.PENDING) for f in files},
        )
        self._jobs[job_id] = tracker
        self._user_jobs[user_id] = job_id
        return tracker

    def get(self, job_id: str) -> JobTracker | None:
        return self._jobs.get(job_id)

    def get_for_user(self, user_id: int) -> JobTracker | None:
        job_id = self._user_jobs.get(user_id)
        return self._jobs.get(job_id) if job_id else None

    async def schedule_cleanup(self, tracker: JobTracker) -> None:
        tracker._cleanup_task = asyncio.create_task(self._cleanup_after_delay(tracker.job_id))

    async def _cleanup_after_delay(self, job_id: str) -> None:
        await asyncio.sleep(900)
        self._jobs.pop(job_id, None)
        for uid, jid in list(self._user_jobs.items()):
            if jid == job_id:
                self._user_jobs.pop(uid, None)


job_registry = JobRegistry()


def create_job(files: list[dict[str, Any]], organization_id: int, user_id: int) -> JobTracker:
    return job_registry.create(files, organization_id, user_id)


def get_job(job_id: str) -> JobTracker | None:
    return job_registry.get(job_id)


def get_user_active_job(user_id: int) -> str | None:
    return job_registry._user_jobs.get(user_id)
