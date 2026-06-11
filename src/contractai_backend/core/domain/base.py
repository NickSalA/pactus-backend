"""BaseTable: Clase base para todas las tablas de la base de datos."""

from sqlalchemy import BigInteger, Column, Identity
from sqlmodel import Field, SQLModel


class BaseTable(SQLModel):
    """Todas las tablas de ContractAI heredarán de aquí."""

    id: int = Field(default=None, primary_key=True, index=True)


class BigIntBaseTable(SQLModel):
    """Clase base para tablas de auditoría y transaccionales que requieren IDs masivos de 64 bits."""

    id: int | None = Field(
        default=None,
        sa_column=Column("id", BigInteger, Identity(always=False), primary_key=True, index=True),
    )
