"""Interface for template draft generators."""

from abc import ABC, abstractmethod
from typing import Any

from ...api.schemas import GenerateTemplateDraftRequest, TemplateDraftResponse


class ITemplateDraftGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        request: GenerateTemplateDraftRequest,
        reference_context: str | None = None,
        reference_outline: dict[str, Any] | None = None,
        organization_context: dict[str, Any] | None = None,
        validation_feedback: list[str] | None = None,
    ) -> TemplateDraftResponse:
        """Genera un borrador de plantilla con contexto opcional."""
        pass
