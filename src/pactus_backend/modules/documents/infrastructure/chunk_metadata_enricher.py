"""Enriches document chunks with metadata needed for vector search."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..application.repositories import DocumentChunkEnricher


class VectorChunkMetadataEnricher(DocumentChunkEnricher):
    def enrich(self, chunks: Sequence[Any], organization_id: int, form_data: Mapping[str, Any]) -> None:
        """Adds vector metadata needed by downstream search."""
        source_metadata = form_data.get("source") if isinstance(form_data, Mapping) else None

        for chunk in chunks:
            metadata = getattr(chunk, "metadata", None)
            if metadata is None:
                metadata = {}
                try:
                    chunk.metadata = metadata
                except (AttributeError, TypeError):
                    continue

            metadata["organization_id"] = str(organization_id)

            if isinstance(source_metadata, Mapping):
                provider = source_metadata.get("provider")
                file_id = source_metadata.get("file_id")

                if provider:
                    metadata["source_provider"] = str(provider)
                if file_id:
                    metadata["source_file_id"] = str(file_id)
