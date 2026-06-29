"""HTTP schemas for third-party integration endpoints."""

from typing import Literal

from pydantic import BaseModel, Field

from ...documents.api.schemas import CreateDocumentDraftRequest
from ..application.jobs import FileStatus


class AuthURLResponse(BaseModel):
    url: str


class TokenResponse(BaseModel):
    token: str
    refresh_token: str | None
    token_uri: str
    client_id: str
    client_secret: str
    scopes: list[str]


class DriveRequest(BaseModel):
    token: dict


class DriveImportFile(BaseModel):
    file_id: str = Field(..., min_length=1)
    document: CreateDocumentDraftRequest = Field(default_factory=CreateDocumentDraftRequest)


class ImportRequest(BaseModel):
    token: dict
    files: list[DriveImportFile] = Field(..., min_length=1)


class ImportResponse(BaseModel):
    message: str
    queued_files: int
    index_name: str
    job_id: str


class ImportEvent(BaseModel):
    type: Literal["initial_state", "file_update", "job_complete"]
    job_id: str
    status: Literal["RUNNING", "COMPLETED", "FAILED"]
    files: list[FileStatus]
    error: str | None = None
