"""Port for best-effort structured document extraction."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from ....catalog.domain.entities import ServiceTable
from ..dto import ExtractedDocumentData


class DocumentStructuredExtractor(ABC):
    @abstractmethod
    async def extract(
        self,
        filename: str,
        chunks: Sequence[Any],
        available_services: Sequence[ServiceTable],
    ) -> ExtractedDocumentData:
        """Extracts nullable structured metadata from parsed document chunks."""
        pass
