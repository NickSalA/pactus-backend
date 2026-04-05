"""Value objects for the templates domain."""

from enum import StrEnum


class TemplateState(StrEnum):
    """Estados permitidos para las plantillas."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"
