"""Supabase Storage implementation for document files."""

import re
from pathlib import Path

import httpx
from httpx import Response

from ....shared.config import settings
from ..application.repositories import DocumentStorageRepository
from ..domain.exceptions import DocumentStorageError, DocumentStorageUnavailableError
from ..domain.value_objs import DocumentType


def sanitize_storage_filename(filename: str) -> str:
    """Sanitizes filenames to a safe storage-friendly format."""
    file_path = Path(filename)
    base_name: str = file_path.stem
    extension: str = file_path.suffix.lower()
    if not extension:
        extension = ".pdf"
    normalized: str = re.sub(pattern=r"[^A-Za-z0-9._-]", repl="_", string=base_name).strip("._")
    if not normalized:
        normalized = "document"
    return f"{normalized}{extension}"


def normalize_storage_document_type(document_type: DocumentType | None) -> str:
    """Maps document types to stable storage prefixes."""
    if document_type is None:
        return "untyped"
    return document_type.value.lower()


def build_document_storage_path(
    document_id: int,
    organization_id: int,
    document_type: DocumentType | None,
    filename: str | None = None,
) -> str:
    """Builds deterministic storage path for each document."""
    resolved_filename = filename or "document.pdf"
    safe_name = sanitize_storage_filename(resolved_filename)
    type_prefix = normalize_storage_document_type(document_type)
    return f"orgs/{organization_id}/{type_prefix}/docs/{document_id}/{safe_name}"


class SupabaseStorageRepository(DocumentStorageRepository):
    """Stores document binaries in Supabase Storage using REST API."""

    def __init__(self, client: httpx.AsyncClient):
        self.base_url: str = settings.SUPABASE_URL.rstrip("/")
        self.bucket: str = settings.SUPABASE_STORAGE_BUCKET
        self.api_key: str = settings.SUPABASE_SECRET_KEY
        self.client: httpx.AsyncClient = client

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitizes filenames to a safe storage-friendly format."""
        return sanitize_storage_filename(filename)

    @staticmethod
    def _normalize_document_type(document_type: DocumentType | None) -> str:
        """Maps document types to stable storage prefixes."""
        return normalize_storage_document_type(document_type)

    def _build_path(
        self,
        document_id: int,
        organization_id: int,
        document_type: DocumentType | None,
        filename: str | None = None,
    ) -> str:
        """Builds deterministic storage path for each document."""
        return build_document_storage_path(
            document_id=document_id,
            organization_id=organization_id,
            document_type=document_type,
            filename=filename,
        )

    async def _post(self, *, url: str, headers: dict[str, str], content: bytes | None = None, json: dict | None = None) -> Response:
        return await self.client.post(url=url, headers=headers, content=content, json=json, timeout=30.0)

    async def _delete(self, *, url: str, headers: dict[str, str]) -> Response:
        return await self.client.delete(url=url, headers=headers, timeout=30.0)

    async def upload_file(
        self,
        document_id: int,
        organization_id: int,
        document_type: DocumentType | None,
        file: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Uploads a document file to Supabase Storage."""
        path: str = self._build_path(document_id, organization_id, document_type, filename)
        endpoint = f"{self.base_url}/storage/v1/object/{self.bucket}/{path}"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        try:
            response = await self._post(url=endpoint, content=file, headers=headers)
        except httpx.TimeoutException as e:
            raise DocumentStorageUnavailableError("El servicio de almacenamiento de documentos no respondió a tiempo.") from e
        except httpx.RequestError as e:
            raise DocumentStorageUnavailableError("No se pudo conectar al servicio de almacenamiento de documentos.") from e
        if response.status_code not in (httpx.codes.OK, httpx.codes.CREATED):
            raise DocumentStorageError("Fallo al subir el archivo al almacenamiento de documentos.")

        return path

    async def delete_file(self, path: str) -> None:
        """Deletes a document file from Supabase Storage if it exists."""
        endpoint = f"{self.base_url}/storage/v1/object/{self.bucket}/{path}"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
        }
        try:
            response = await self._delete(url=endpoint, headers=headers)
        except httpx.TimeoutException as e:
            raise DocumentStorageUnavailableError("El servicio de almacenamiento de documentos no respondió a tiempo.") from e
        except httpx.RequestError as e:
            raise DocumentStorageUnavailableError("No se pudo conectar al servicio de almacenamiento de documentos.") from e
        if response.status_code not in (httpx.codes.OK, httpx.codes.NO_CONTENT):
            normalized_body: str = response.text.lower()
            object_not_found = (
                response.status_code == httpx.codes.NOT_FOUND
                or (response.status_code == httpx.codes.BAD_REQUEST and "not_found" in normalized_body)
                or (response.status_code == httpx.codes.BAD_REQUEST and "object not found" in normalized_body)
            )

            if object_not_found:
                return

            raise DocumentStorageError("Fallo al eliminar el archivo del almacenamiento de documentos.")

    async def create_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Creates a signed URL for temporary access to a document file."""
        endpoint = f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{path}"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
        }

        payload: dict[str, int] = {"expiresIn": expires_in}

        try:
            response = await self._post(url=endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise DocumentStorageUnavailableError("El servicio de almacenamiento de documentos no respondió a tiempo.") from e
        except httpx.RequestError as e:
            raise DocumentStorageUnavailableError("No se pudo conectar al servicio de almacenamiento de documentos.") from e

        if response.status_code != httpx.codes.OK:
            raise DocumentStorageError("Fallo al generar la URL firmada para el archivo del almacenamiento de documentos.")

        data = response.json()
        signed_url = data.get("signedURL")
        if not signed_url:
            raise DocumentStorageError("La respuesta del almacenamiento de documentos no contiene la URL firmada.")

        return f"{self.base_url}/storage/v1{signed_url}"
