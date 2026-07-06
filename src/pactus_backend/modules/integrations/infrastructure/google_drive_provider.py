import asyncio
import io

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from ....modules.integrations.application import ICloudIntegrationProvider
from ....modules.integrations.domain import CloudFileNotFoundError, CloudStorageIntegrationError, InvalidCloudTokenError

GOOGLE_DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class GoogleDriveProvider(ICloudIntegrationProvider):
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = [GOOGLE_DRIVE_FILE_SCOPE]
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }

    def get_auth_url(self) -> str:
        flow = Flow.from_client_config(self.client_config, scopes=self.scopes)
        flow.redirect_uri = self.redirect_uri
        flow.autogenerate_code_verifier = False
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        return auth_url

    def _exchange_sync(self, code: str) -> dict:
        try:
            flow = Flow.from_client_config(self.client_config, scopes=self.scopes)
            flow.redirect_uri = self.redirect_uri
            flow.autogenerate_code_verifier = False
            flow.fetch_token(code=code)
            credentials = flow.credentials
            return {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
        except Exception as e:
            raise InvalidCloudTokenError("El código de autorización proporcionado es inválido o ha expirado.") from e

    async def exchange_code_for_token(self, code: str) -> dict:
        return await asyncio.to_thread(self._exchange_sync, code)

    def _list_files_sync(self, token: dict, folder_id: str | None) -> list[dict]:
        try:
            creds = Credentials(**token)
            service = build("drive", "v3", credentials=creds)

            query = "trashed = false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            else:
                query += " and 'root' in parents"

            results = service.files().list(q=query, spaces="drive", fields="files(id, name, mimeType)").execute()
            return results.get("files", [])
        except HttpError as e:
            if e.resp.status in [401, 403]:
                raise InvalidCloudTokenError() from e
            raise CloudStorageIntegrationError(f"Error al listar archivos: {e.reason}") from e
        except GoogleAuthError as e:
            raise InvalidCloudTokenError() from e
        except Exception as e:
            raise CloudStorageIntegrationError(str(e)) from e

    async def list_files(self, token: dict, folder_id: str | None = None) -> list[dict]:
        return await asyncio.to_thread(self._list_files_sync, token, folder_id)

    def _get_file_metadata_sync(self, token: dict, file_id: str) -> dict:
        try:
            creds = Credentials(**token)
            service = build("drive", "v3", credentials=creds)

            file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType, webViewLink").execute()

            return file_metadata
        except HttpError as e:
            if e.resp.status == 404:
                raise CloudFileNotFoundError(f"El archivo con ID {file_id} no se encontró.") from e
            if e.resp.status in [401, 403]:
                raise InvalidCloudTokenError() from e
            raise CloudStorageIntegrationError(f"Error al obtener metadatos: {e.reason}") from e
        except GoogleAuthError as e:
            raise InvalidCloudTokenError() from e
        except Exception as e:
            raise CloudStorageIntegrationError(str(e)) from e

    async def get_file_metadata(self, token: dict, file_id: str) -> dict:
        return await asyncio.to_thread(self._get_file_metadata_sync, token, file_id)

    def _download_file_sync(self, token: dict, file_id: str) -> bytes:
        try:
            creds = Credentials(**token)
            service = build("drive", "v3", credentials=creds)

            file_metadata = service.files().get(fileId=file_id, fields="mimeType").execute()
            mime_type = file_metadata.get("mimeType", "")

            if mime_type.startswith("application/vnd.google-apps."):
                request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
            else:
                request = service.files().get_media(fileId=file_id)

            file_stream = io.BytesIO()
            downloader = MediaIoBaseDownload(file_stream, request)

            done = False
            while not done:
                _status, done = downloader.next_chunk()

            return file_stream.getvalue()
        except HttpError as e:
            if e.resp.status == 404:
                raise CloudFileNotFoundError(f"El archivo con ID {file_id} no se encontró para su descarga.") from e
            if e.resp.status in [401, 403]:
                raise InvalidCloudTokenError() from e
            raise CloudStorageIntegrationError(f"Error al descargar archivo: {e.reason}") from e
        except GoogleAuthError as e:
            raise InvalidCloudTokenError() from e
        except Exception as e:
            raise CloudStorageIntegrationError(str(e)) from e

    async def download_file(self, token: dict, file_id: str) -> bytes:
        return await asyncio.to_thread(self._download_file_sync, token, file_id)
