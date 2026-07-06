"""Persistent entities for audit tables."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlmodel import Field

from ....core.domain.base import BigIntBaseTable
from ....core.domain.db_schemas import AUDIT_SCHEMA, CHATBOT_SCHEMA, CONTRACTS_SCHEMA, IDENTITY_SCHEMA, TEMPLATES_SCHEMA
from .value_objs import AITokenSource, AuditChatbotAction, AuditContractAction, AuditTemplateAction, AuditUserAction


class UserActivityTable(BigIntBaseTable, table=True):
    """Audit trail for organization user management actions."""

    __tablename__ = "user_activity"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    actor_name: str | None = Field(default=None, sa_column=Column("actor_name", String, nullable=True))
    actor_role: str = Field(sa_column=Column("actor_role", String, nullable=False))
    action: AuditUserAction = Field(
        sa_column=Column(
            "action",
            ENUM(AuditUserAction, name="audit_user_action", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    target_user_id: int | None = Field(
        default=None,
        sa_column=Column(
            "target_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    target_user_email: str | None = Field(default=None, sa_column=Column("target_user_email", String, nullable=True))
    target_user_name: str | None = Field(default=None, sa_column=Column("target_user_name", String, nullable=True))
    previous_role: str | None = Field(default=None, sa_column=Column("previous_role", String, nullable=True))
    role: str | None = Field(default=None, sa_column=Column("role", String, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )


class ChatbotActivityTable(BigIntBaseTable, table=True):
    """Audit trail for chatbot usage activity."""

    __tablename__ = "chatbot_activity"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    actor_name: str | None = Field(default=None, sa_column=Column("actor_name", String, nullable=True))
    actor_role: str = Field(sa_column=Column("actor_role", String, nullable=False))
    action: AuditChatbotAction = Field(
        sa_column=Column(
            "action",
            ENUM(AuditChatbotAction, name="audit_chatbot_action", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    conversation_id: int | None = Field(
        default=None,
        sa_column=Column(
            "conversation_id",
            BigInteger,
            ForeignKey(f"{CHATBOT_SCHEMA}.conversations.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )

class TemplateActivityTable(BigIntBaseTable, table=True):
    __tablename__ = "template_activity"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    actor_name: str | None = Field(default=None, sa_column=Column("actor_name", String, nullable=True))
    actor_role: str = Field(sa_column=Column("actor_role", String, nullable=False))
    action: AuditTemplateAction = Field(
        sa_column=Column(
            "action",
            ENUM(AuditTemplateAction, name="audit_template_action", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    template_id: int | None = Field(
        default=None,
        sa_column=Column(
            "template_id",
            BigInteger,
            ForeignKey(f"{TEMPLATES_SCHEMA}.document_templates.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    template_format_id: int | None = Field(
        default=None,
        sa_column=Column(
            "template_format_id",
            BigInteger,
            ForeignKey(f"{TEMPLATES_SCHEMA}.template_formats.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    template_name: str | None = Field(default=None, sa_column=Column("template_name", String(255), nullable=True))
    document_type: str | None = Field(default=None, sa_column=Column("document_type", String(50), nullable=True))
    previous_state: str | None = Field(default=None, sa_column=Column("previous_state", String(50), nullable=True))
    state: str | None = Field(default=None, sa_column=Column("state", String(50), nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )


class ContractActivityTable(BigIntBaseTable, table=True):
    __tablename__ = "contract_activity"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    actor_name: str | None = Field(default=None, sa_column=Column("actor_name", String, nullable=True))
    actor_role: str = Field(sa_column=Column("actor_role", String, nullable=False))
    action: AuditContractAction = Field(
        sa_column=Column(
            "action",
            ENUM(AuditContractAction, name="audit_contract_action", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    document_id: int | None = Field(
        default=None,
        sa_column=Column(
            "document_id",
            BigInteger,
            ForeignKey(f"{CONTRACTS_SCHEMA}.documents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    company_contract_id: int | None = Field(
        default=None,
        sa_column=Column(
            "company_contract_id",
            BigInteger,
            ForeignKey(f"{CONTRACTS_SCHEMA}.company_contracts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    labor_contract_id: int | None = Field(
        default=None,
        sa_column=Column(
            "labor_contract_id",
            BigInteger,
            ForeignKey(f"{CONTRACTS_SCHEMA}.labor_contracts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    document_name: str | None = Field(default=None, sa_column=Column("document_name", String(255), nullable=True))
    document_type: str | None = Field(default=None, sa_column=Column("document_type", String(50), nullable=True))
    previous_state: str | None = Field(default=None, sa_column=Column("previous_state", String(50), nullable=True))
    state: str | None = Field(default=None, sa_column=Column("state", String(50), nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )

class AITokenUsageTable(BigIntBaseTable, table=True):
    """Audit trail for global AI token usage."""

    __tablename__ = "ai_token_usage"
    __table_args__: ClassVar[dict[str, str]] = {"schema": AUDIT_SCHEMA}
    organization_id: int = Field(
        sa_column=Column(
            "organization_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    actor_user_id: int = Field(
        sa_column=Column(
            "actor_user_id",
            BigInteger,
            ForeignKey(f"{IDENTITY_SCHEMA}.users.id"),
            nullable=False,
            index=True,
        )
    )
    source: AITokenSource = Field(
        sa_column=Column(
            "source",
            ENUM(AITokenSource, name="ai_token_source", schema=AUDIT_SCHEMA, create_type=False),
            nullable=False,
            index=True,
        )
    )
    input_tokens: int | None = Field(default=None, sa_column=Column("input_tokens", Integer, nullable=True))
    output_tokens: int | None = Field(default=None, sa_column=Column("output_tokens", Integer, nullable=True))
    total_tokens: int | None = Field(default=None, sa_column=Column("total_tokens", Integer, nullable=True))
    input_cost_usd: Decimal | None = Field(default=None, sa_column=Column("input_cost_usd", Numeric, nullable=True))
    output_cost_usd: Decimal | None = Field(default=None, sa_column=Column("output_cost_usd", Numeric, nullable=True))
    total_cost_usd: Decimal | None = Field(default=None, sa_column=Column("total_cost_usd", Numeric, nullable=True))
    model_used: str | None = Field(default=None, sa_column=Column("model_used", String, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    )
