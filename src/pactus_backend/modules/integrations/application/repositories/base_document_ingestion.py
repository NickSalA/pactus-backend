from abc import ABC, abstractmethod
from typing import Any


class IDocumentIngestionTarget(ABC):
    @abstractmethod
    async def ingest_drive_file(
        self,
        document_payload: dict[str, Any],
        file_bytes: bytes,
        filename: str,
        content_type: str,
        organization_id: int,
        source_metadata: dict[str, Any],
        index_name: str,
        actor: Any | None = None,
    ) -> Any:
        pass
