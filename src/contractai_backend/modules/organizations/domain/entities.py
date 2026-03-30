"""Database models for organizations."""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, String, Text
from sqlmodel import Field

from contractai_backend.core.domain.base import BaseTable


class OrganizationTable(BaseTable, table=True):
    __tablename__ = "organizations"

    name: str = Field(sa_column=Column("name", String(255), nullable=False, unique=True))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, default=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    ruc: str = Field(sa_column=Column("ruc", String(20), nullable=True))
    address: str = Field(sa_column=Column("address", Text, nullable=True))
    company_type: str = Field(sa_column=Column("company_type", Text, nullable=True))
    objeto_social: str = Field(sa_column=Column("objeto_social", Text, nullable=True))
    legal_rep_name: str = Field(sa_column=Column("legal_rep_name", String(255), nullable=True))
    legal_rep_dni: str = Field(sa_column=Column("legal_rep_dni", String(100), nullable=True))
    jurisdiction: str = Field(sa_column=Column("jurisdiction", String(255), nullable=True))
    city: str = Field(sa_column=Column("city", String(100), nullable=True))
    autorizacion_entidad: str = Field(sa_column=Column("autorizacion_entidad", Text, nullable=True))
    autorizacion_fecha: date = Field(default=None, sa_column=Column("autorizacion_fecha", Date, nullable=True))
    autorizacion_emitida_por: str = Field(sa_column=Column("autorizacion_emitida_por", Text, nullable=True))
    email: str = Field(sa_column=Column("email", String(255), nullable=True))
    phone: str = Field(sa_column=Column("phone", String(20), nullable=True))
