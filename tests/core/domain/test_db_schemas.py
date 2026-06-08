"""Tests for persistent table schema metadata."""

from contractai_backend.core.domain.db_schemas import (
    APP_TYPES_SCHEMA,
    AUDIT_SCHEMA,
    CATALOG_SCHEMA,
    CHATBOT_SCHEMA,
    CONTRACTS_SCHEMA,
    IDENTITY_SCHEMA,
    NOTIFICATIONS_SCHEMA,
    TELEMETRY_SCHEMA,
    TEMPLATES_SCHEMA,
)
from contractai_backend.modules.audit.domain.entities import UserActivityTable
from contractai_backend.modules.catalog.domain.entities import ServiceTable
from contractai_backend.modules.chatbot.domain.entities import ChatbotTokenUsage, ConversationTable
from contractai_backend.modules.documents.domain import (
    CompanyContractServiceTable,
    CompanyContractTable,
    DocumentTable,
    LaborContractTable,
)
from contractai_backend.modules.folders.domain.entities import FolderTable
from contractai_backend.modules.notifications.domain import NotificationRuleTable, NotificationSendLog
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.templates.domain.entities import TemplateFormatTable, TemplateTable
from contractai_backend.modules.users.domain.entities import UserTable


def test_application_tables_use_granular_schemas() -> None:
    assert OrganizationTable.__table__.schema == IDENTITY_SCHEMA
    assert UserTable.__table__.schema == IDENTITY_SCHEMA
    assert UserActivityTable.__table__.schema == AUDIT_SCHEMA
    assert ServiceTable.__table__.schema == CATALOG_SCHEMA
    assert FolderTable.__table__.schema == CONTRACTS_SCHEMA
    assert DocumentTable.__table__.schema == CONTRACTS_SCHEMA
    assert CompanyContractTable.__table__.schema == CONTRACTS_SCHEMA
    assert LaborContractTable.__table__.schema == CONTRACTS_SCHEMA
    assert CompanyContractServiceTable.__table__.schema == CONTRACTS_SCHEMA
    assert TemplateTable.__table__.schema == TEMPLATES_SCHEMA
    assert TemplateFormatTable.__table__.schema == TEMPLATES_SCHEMA
    assert NotificationRuleTable.__table__.schema == NOTIFICATIONS_SCHEMA
    assert NotificationSendLog.__table__.schema == NOTIFICATIONS_SCHEMA
    assert ConversationTable.__table__.schema == CHATBOT_SCHEMA
    assert ChatbotTokenUsage.__table__.schema == TELEMETRY_SCHEMA


def test_shared_postgres_enums_use_app_types_schema() -> None:
    assert UserTable.__table__.c.role.type.schema == APP_TYPES_SCHEMA
    assert FolderTable.__table__.c.owner_role.type.schema == APP_TYPES_SCHEMA
    assert DocumentTable.__table__.c.state.type.schema == APP_TYPES_SCHEMA
    assert LaborContractTable.__table__.c.salary_currency.type.schema == APP_TYPES_SCHEMA
    assert CompanyContractServiceTable.__table__.c.currency.type.schema == APP_TYPES_SCHEMA
    assert TemplateTable.__table__.c.document_type.type.schema == APP_TYPES_SCHEMA
    assert TemplateTable.__table__.c.state.type.schema == APP_TYPES_SCHEMA
    assert TemplateFormatTable.__table__.c.document_type.type.schema == APP_TYPES_SCHEMA
    assert UserActivityTable.__table__.c.action.type.schema == AUDIT_SCHEMA


def test_cross_schema_foreign_keys_are_qualified() -> None:
    foreign_key_targets = {
        foreign_key.target_fullname
        for table in (DocumentTable, CompanyContractServiceTable, ChatbotTokenUsage, UserActivityTable)
        for foreign_key in table.__table__.foreign_keys
    }

    assert f"{IDENTITY_SCHEMA}.organizations.id" in foreign_key_targets
    assert f"{CATALOG_SCHEMA}.services.id" in foreign_key_targets
    assert f"{CHATBOT_SCHEMA}.conversations.id" in foreign_key_targets
    assert f"{IDENTITY_SCHEMA}.users.id" in foreign_key_targets
