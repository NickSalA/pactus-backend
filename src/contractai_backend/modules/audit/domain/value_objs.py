"""Value objects for audit activity."""

from enum import StrEnum


class AuditUserAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class AuditChatbotAction(StrEnum):
    CONVERSATION_STARTED = "CONVERSATION_STARTED"
    MESSAGE_SENT = "MESSAGE_SENT"
    RESPONSE_GENERATED = "RESPONSE_GENERATED"
