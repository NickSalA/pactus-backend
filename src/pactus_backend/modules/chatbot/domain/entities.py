"""Domain entities for chatbot module."""

from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from ....core.domain.base import BaseTable
from ....core.domain.db_schemas import CHATBOT_SCHEMA, IDENTITY_SCHEMA


class Message(BaseModel):
    role: str
    content: str
    chart: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    def as_record(self) -> dict[str, Any]:
        """Serialize the message into the JSON-compatible payload stored in the DB."""
        return self.model_dump(mode="json", exclude_none=True)


class ConversationTable(BaseTable, table=True):
    __tablename__: str = "conversations"
    __table_args__: ClassVar[dict[str, str]] = {"schema": CHATBOT_SCHEMA}

    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            Integer,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    user_id: int = Field(
        sa_column=Column(
            "user_id",
            Integer,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    title: str = Field(sa_column=Column("title", String, nullable=False))
    content: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column("content", JSONB, nullable=False, server_default="[]"))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC), sa_column=Column("created_at", DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC), sa_column=Column("updated_at", DateTime(timezone=True), nullable=False)
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Valida que el título de la conversación no esté vacío o solo contenga espacios."""
        if not v or not v.strip():
            raise ValueError("El título de la conversación no puede estar vacío.")
        return v.strip()

    @field_validator("organization_id", "user_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """Valida que los IDs de organización y usuario sean números enteros positivos."""
        if v <= 0:
            raise ValueError("El ID debe ser un número entero positivo.")
        return v
