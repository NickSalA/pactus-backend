"""DTOs relacionados con la autenticación de usuarios externos (e.g., Supabase)."""

from uuid import UUID

from pydantic import BaseModel


class ExternalUserDTO(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
