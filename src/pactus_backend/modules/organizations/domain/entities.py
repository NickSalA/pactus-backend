"""Database models for organizations."""

from datetime import UTC, date, datetime
from typing import ClassVar

from sqlalchemy import Boolean, Column, Date, DateTime, String, Text
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import IDENTITY_SCHEMA


class OrganizationTable(BaseTable, table=True):
    __tablename__ = "organizations"
    __table_args__: ClassVar[dict[str, str]] = {"schema": IDENTITY_SCHEMA}

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
    ruc: str | None = Field(default=None, sa_column=Column("ruc", String(20), nullable=True))
    address: str | None = Field(default=None, sa_column=Column("address", Text, nullable=True))
    company_type: str | None = Field(default=None, sa_column=Column("company_type", Text, nullable=True))
    objeto_social: str | None = Field(default=None, sa_column=Column("objeto_social", Text, nullable=True))
    legal_rep_name: str | None = Field(default=None, sa_column=Column("legal_rep_name", String(255), nullable=True))
    legal_rep_dni: str | None = Field(default=None, sa_column=Column("legal_rep_dni", String(100), nullable=True))
    jurisdiction: str | None = Field(default=None, sa_column=Column("jurisdiction", String(255), nullable=True))
    city: str | None = Field(default=None, sa_column=Column("city", String(100), nullable=True))
    autorizacion_entidad: str | None = Field(default=None, sa_column=Column("autorizacion_entidad", Text, nullable=True))
    autorizacion_fecha: date | None = Field(default=None, sa_column=Column("autorizacion_fecha", Date, nullable=True))
    autorizacion_emitida_por: str | None = Field(default=None, sa_column=Column("autorizacion_emitida_por", Text, nullable=True))
    email: str | None = Field(default=None, sa_column=Column("email", String(255), nullable=True))
    phone: str | None = Field(default=None, sa_column=Column("phone", String(20), nullable=True))
    paypal_subscription_id: str | None = Field(default=None, sa_column=Column("paypal_subscription_id", String(128), nullable=True))
