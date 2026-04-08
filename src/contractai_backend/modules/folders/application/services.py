"""Service layer for role-scoped document folders."""

from collections.abc import Sequence
from datetime import UTC, datetime

from ....core.exceptions.base import ConflictError, ForbiddenError, NotFoundError
from ...users.domain.entities import UserTable
from ...users.domain.value_objs import UserRole
from ..api.schemas import FolderCreateRequest, FolderResponse, FolderUpdateRequest
from ..domain.entities import FolderTable
from ..domain.access_policy import can_create_folder, can_manage_folder, can_read_folder
from .repositories import FolderRepository


class FolderService:
    """Handles folder listing and administration with role-based visibility."""

    def __init__(self, sql_repo: FolderRepository):
        self.sql_repo = sql_repo

    @staticmethod
    def _resolve_visible_owner_roles(user_role: UserRole) -> Sequence[UserRole] | None:
        if user_role == UserRole.ADMIN:
            return None
        if user_role == UserRole.HR:
            return [UserRole.HR]
        return [UserRole.MANAGER]

    @staticmethod
    def _serialize(
        folder: FolderTable,
        *,
        creator_name: str | None,
        creator_email: str | None,
        documents_count: int,
    ) -> FolderResponse:
        return FolderResponse(
            id=folder.id,
            organization_id=folder.organization_id,
            name=folder.name,
            owner_role=folder.owner_role,
            created_by=folder.created_by,
            created_by_name=creator_name,
            created_by_email=creator_email,
            documents_count=documents_count,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )

    async def _build_responses(self, folders: Sequence[FolderTable]) -> Sequence[FolderResponse]:
        if not folders:
            return []

        folder_ids = [folder.id for folder in folders if folder.id is not None]
        creator_ids = [folder.created_by for folder in folders]

        document_counts = await self.sql_repo.count_documents_by_folder_ids(
            organization_id=folders[0].organization_id,
            folder_ids=folder_ids,
        )
        creators = await self.sql_repo.get_users_by_ids(creator_ids) if creator_ids else []
        creators_by_id = {creator.id: creator for creator in creators if creator.id is not None}

        results: list[FolderResponse] = []
        for folder in folders:
            if folder.id is None:
                continue
            creator = creators_by_id.get(folder.created_by)
            results.append(
                self._serialize(
                    folder,
                    creator_name=creator.full_name if creator else None,
                    creator_email=creator.email if creator else None,
                    documents_count=document_counts.get(folder.id, 0),
                )
            )
        return results

    async def list_folders(self, current_user: UserTable) -> Sequence[FolderResponse]:
        """Lists folders visible to the current user."""
        owner_roles = self._resolve_visible_owner_roles(current_user.role)
        folders = await self.sql_repo.get_folders(current_user.organization_id, owner_roles=owner_roles)
        return await self._build_responses(folders)

    async def create_folder(self, current_user: UserTable, data: FolderCreateRequest) -> FolderResponse:
        """Creates a folder in the current user's role scope."""
        if not can_create_folder(current_user.role):
            raise ForbiddenError("Solo RRHH y Manager pueden crear carpetas")

        existing = await self.sql_repo.get_folder_by_name(current_user.organization_id, current_user.role, data.name)
        if existing is not None:
            raise ConflictError("Ya existe una carpeta con ese nombre para este rol")

        folder = await self.sql_repo.save_folder(
            FolderTable(
                organization_id=current_user.organization_id,
                name=data.name,
                owner_role=current_user.role,
                created_by=current_user.id,
            )
        )
        return self._serialize(
            folder,
            creator_name=current_user.full_name,
            creator_email=current_user.email,
            documents_count=0,
        )

    async def update_folder(
        self,
        current_user: UserTable,
        folder_id: int,
        data: FolderUpdateRequest,
    ) -> FolderResponse:
        """Updates a folder if the user can manage its role scope."""
        folder = await self.sql_repo.get_folder_by_id(folder_id)
        if folder is None or folder.organization_id != current_user.organization_id:
            raise NotFoundError("La carpeta solicitada no existe en la organización actual")
        if not can_read_folder(current_user.role, folder.owner_role):
            raise NotFoundError("La carpeta solicitada no existe en la organización actual")
        if not can_manage_folder(current_user.role, folder.owner_role):
            raise ForbiddenError("No tiene permisos para editar esta carpeta")

        if data.name is not None and data.name.lower() != folder.name.lower():
            existing = await self.sql_repo.get_folder_by_name(current_user.organization_id, folder.owner_role, data.name)
            if existing is not None and existing.id != folder.id:
                raise ConflictError("Ya existe una carpeta con ese nombre para este rol")
            folder.name = data.name

        folder.updated_at = datetime.now(UTC)
        updated_folder = await self.sql_repo.update_folder(folder)
        creators = await self.sql_repo.get_users_by_ids([updated_folder.created_by])
        creator = creators[0] if creators else None
        document_counts = await self.sql_repo.count_documents_by_folder_ids(
            organization_id=current_user.organization_id,
            folder_ids=[updated_folder.id] if updated_folder.id is not None else [],
        )
        return self._serialize(
            updated_folder,
            creator_name=creator.full_name if creator is not None else None,
            creator_email=creator.email if creator is not None else None,
            documents_count=document_counts.get(updated_folder.id, 0),
        )

    async def delete_folder(self, current_user: UserTable, folder_id: int) -> None:
        """Deletes one folder if the current user can manage it."""
        folder = await self.sql_repo.get_folder_by_id(folder_id)
        if folder is None or folder.organization_id != current_user.organization_id:
            raise NotFoundError("La carpeta solicitada no existe en la organización actual")
        if not can_read_folder(current_user.role, folder.owner_role):
            raise NotFoundError("La carpeta solicitada no existe en la organización actual")
        if not can_manage_folder(current_user.role, folder.owner_role):
            raise ForbiddenError("No tiene permisos para eliminar esta carpeta")

        deleted = await self.sql_repo.delete_folder(folder_id)
        if not deleted:
            raise NotFoundError("La carpeta solicitada no existe en la organización actual")
