"""Defines the base interface for document chunk enrichers."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any


class DocumentChunkEnricher(ABC):
    @abstractmethod
    def enrich(self, chunks: Sequence[Any], organization_id: int, form_data: Mapping[str, Any]) -> None:
        """Adds metadata required by downstream vector infrastructure."""
        pass
