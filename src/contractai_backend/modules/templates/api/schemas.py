"""Schemas for template authoring endpoints."""

from ...documents.api.schemas import DocumentResponse
from ..application.dto import (
    GenerateTemplateDraftRequest as ApplicationGenerateTemplateDraftRequest,
)
from ..application.dto import (
    PersistedTemplateDraftResponse as ApplicationPersistedTemplateDraftResponse,
)
from ..application.dto import (
    PreviewTemplateRequest as ApplicationPreviewTemplateRequest,
)
from ..application.dto import (
    PreviewTemplateResponse as ApplicationPreviewTemplateResponse,
)
from ..application.dto import (
    TemplateDraftResponse as ApplicationTemplateDraftResponse,
)
from ..application.dto import (
    TemplateFormatResponse as ApplicationTemplateFormatResponse,
)
from ..application.dto import (
    TemplateResponse as ApplicationTemplateResponse,
)
from ..application.dto import (
    TemplateUsage as ApplicationTemplateUsage,
)
from ..application.dto import (
    UpdateTemplateRequest as ApplicationUpdateTemplateRequest,
)
from ..application.dto import (
    build_template_response,
)


class GenerateTemplateDraftRequest(ApplicationGenerateTemplateDraftRequest):
    """HTTP request body for draft template generation."""


class TemplateUsage(ApplicationTemplateUsage):
    """HTTP response schema for model token usage."""


class TemplateDraftResponse(ApplicationTemplateDraftResponse):
    """HTTP response schema for generated template drafts."""


class TemplateResponse(ApplicationTemplateResponse):
    """HTTP response schema for persisted templates."""


class PersistedTemplateDraftResponse(ApplicationPersistedTemplateDraftResponse):
    """HTTP response schema for persisted generated template drafts."""


class PreviewTemplateRequest(ApplicationPreviewTemplateRequest):
    """HTTP request body for template previews."""


class PreviewTemplateResponse(ApplicationPreviewTemplateResponse):
    """HTTP response schema for template previews."""





class UpdateTemplateRequest(ApplicationUpdateTemplateRequest):
    """HTTP request body for updating templates."""


class TemplateFormatResponse(ApplicationTemplateFormatResponse):
    """HTTP response schema for available template formats."""

__all__ = [
    "DocumentResponse",
    "GenerateTemplateDraftRequest",
    "PersistedTemplateDraftResponse",
    "PreviewTemplateRequest",
    "PreviewTemplateResponse",
    "TemplateDraftResponse",
    "TemplateFormatResponse",
    "TemplateResponse",
    "TemplateUsage",
    "UpdateTemplateRequest",
    "build_template_response",
]
