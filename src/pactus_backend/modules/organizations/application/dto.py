"""Application DTOs for organizations."""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from ....modules.users.application.dto.user_response import UserResponse
from ....modules.users.domain.value_objs import UserRole

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrganizationProvisionRequest(BaseModel):
    name: str
    admin_email: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El nombre de la organizacion es obligatorio")
        return normalized

    @field_validator("admin_email")
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            raise ValueError("El correo del administrador no es valido")
        return normalized


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

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("El nombre de la organizacion no puede estar vacio")
        return normalized

    @field_validator("ruc")
    @classmethod
    def validate_ruc(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and not re.fullmatch(r"\d{11}", normalized):
            raise ValueError("El RUC debe tener exactamente 11 digitos")
        return normalized or None

    @field_validator("legal_rep_dni")
    @classmethod
    def validate_legal_rep_dni(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and not re.fullmatch(r"\d{8}", normalized):
            raise ValueError("El DNI debe tener exactamente 8 digitos")
        return normalized or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized and not re.fullmatch(r"\d{9}", normalized):
            raise ValueError("El telefono debe tener exactamente 9 digitos")
        return normalized or None


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
