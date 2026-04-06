"""Interface for template draft generators."""

from abc import ABC, abstractmethod
from typing import Any

from ...api.schemas import GenerateTemplateDraftRequest, TemplateDraftResponse


class ITemplateDraftGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        request: GenerateTemplateDraftRequest,
        reference_markdown: str | None = None,
        organization_context: dict[str, Any] | None = None,
    ) -> TemplateDraftResponse:
        """Genera un borrador de plantilla a partir de instrucciones y, opcionalmente, un contrato de referencia."""
        pass
