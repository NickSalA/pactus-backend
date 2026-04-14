"""Value objects for the templates domain."""

from enum import StrEnum


class TemplateState(StrEnum):
    """Estados permitidos para las plantillas."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class TemplateGenerationMode(StrEnum):
    """How strictly draft generation should follow the reference."""

    STRICT = "strict"
    ADAPTIVE = "adaptive"


class TemplateFieldMode(StrEnum):
    """How aggressively draft generation should minimize manual fields."""

    EXACT = "exact"
    MINIMAL = "minimal"
