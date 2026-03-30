"""LlamaParse-based document parser implementation."""

import tempfile
from pathlib import Path

from llama_cloud import AsyncLlamaCloud
from llama_cloud.types.file_create_response import FileCreateResponse
from llama_cloud.types.parsing_get_response import ParsingGetResponse
from llama_index.core.schema import Document

from ....shared.config import settings
from ..application.repositories import DocumentExtractor
from ..domain.exceptions import DocumentExtractionError


class LlamaParseExtractor(DocumentExtractor):
    def __init__(
        self,
    ):
        self.parser = AsyncLlamaCloud(
            api_key=settings.LLAMA_PARSE_API_KEY,
            max_retries=3,
        )

    async def extract(self, file: bytes, filename: str) -> list[Document]:
        """Extracts structured data from a document using LlamaParse."""
        extension: str = Path(filename).suffix.lower()
        temp_path = None

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            temp_file.write(file)
            temp_file.flush()
            temp_path: str = temp_file.name
        try:
            documents: FileCreateResponse = await self.parser.files.create(file=Path(temp_path), purpose="parse")

            result: ParsingGetResponse = await self.parser.parsing.parse(
                file_id=documents.id,
                tier="agentic",
                version="latest",
                agentic_options={
                    "custom_prompt": ("Este es un contrato laboral peruano oficial. Conserva las negritas de los títulos y las cláusulas originales.")
                },
                processing_options={"ocr_parameters": {"languages": ["es"]}},
                expand=["markdown"],
            )
            if not result.markdown or not result.markdown.pages:
                raise DocumentExtractionError(f"No se pudo extraer contenido de '{filename}' con LlamaParse.")

            return [
                Document(
                    text=page.markdown,
                    metadata={
                        "filename": filename,
                        "page_number": i + 1,
                        "total_pages": len(result.markdown.pages),
                    },
                )
                for i, page in enumerate(iterable=result.markdown.pages)
            ]

        except Exception as e:
            raise DocumentExtractionError(f"El servicio fallo al procesar '{filename}': {e!s}") from e
        finally:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
