"""Value objects for user audit activity."""

from enum import StrEnum


class AuditUserAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
