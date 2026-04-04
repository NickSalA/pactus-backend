from .base_draft_generator import ITemplateDraftGenerator
from .base_generate import IDocumentGenerator
from .base_relational import IDocumentModuleAdapter, IOrganizationRepository, ITemplateRepository
from .base_render import ITemplateRenderer

__all__ = [
    "IDocumentGenerator",
    "IDocumentModuleAdapter",
    "ITemplateDraftGenerator",
    "IOrganizationRepository",
    "ITemplateRenderer",
    "ITemplateRepository",
]
