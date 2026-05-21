"""Application DTOs for organizations."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.users.application.dto.user_response import UserResponse
from contractai_backend.modules.users.domain.value_objs import UserRole


class OrganizationCreateRequest(BaseModel):
    name: str
    ruc: str | None = None
    address: str | None = None
    company_type: str | None = None
    objeto_social: str | None = None
    legal_rep_name: str | None = None
    legal_rep_dni: str | None = None
    jurisdiction: str | None = None
    city: str | None = None
    autorizacion_entidad: str | None = None
    autorizacion_fecha: date | None = None
    autorizacion_emitida_por: str | None = None
    email: str | None = None
    phone: str | None = None


class OrganizationUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    ruc: str | None = None
    address: str | None = None
    company_type: str | None = None
    objeto_social: str | None = None
    legal_rep_name: str | None = None
    legal_rep_dni: str | None = None
    jurisdiction: str | None = None
    city: str | None = None
    autorizacion_entidad: str | None = None
    autorizacion_fecha: date | None = None
    autorizacion_emitida_por: str | None = None
    email: str | None = None
    phone: str | None = None


class OrganizationResponse(BaseModel):
    """Read model for organization responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    ruc: str | None = None
    address: str | None = None
    company_type: str | None = None
    objeto_social: str | None = None
    legal_rep_name: str | None = None
    legal_rep_dni: str | None = None
    jurisdiction: str | None = None
    city: str | None = None
    autorizacion_entidad: str | None = None
    autorizacion_fecha: date | None = None
    autorizacion_emitida_por: str | None = None
    email: str | None = None
    phone: str | None = None


class OrganizationMemberCreateRequest(BaseModel):
    email: str
    role: UserRole


class OrganizationMemberRoleUpdateRequest(BaseModel):
    role: UserRole


class OrganizationMemberNotificationsUpdateRequest(BaseModel):
    receives_notifications: bool


class OrganizationMemberResponse(UserResponse):
    """Read model for organization members."""
