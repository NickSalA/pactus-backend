"""Tests for the LlamaParse extractor using mocked cloud calls."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pactus_backend.modules.documents.domain.exceptions import DocumentExtractionError
from pactus_backend.modules.documents.infrastructure.llama_parser import LlamaParseExtractor


def _make_extractor() -> LlamaParseExtractor:
    with patch("pactus_backend.modules.documents.infrastructure.llama_parser.settings") as mock_settings:
        mock_settings.LLAMA_PARSE_API_KEY = "fake-key"
        with patch("pactus_backend.modules.documents.infrastructure.llama_parser.AsyncLlamaCloud") as mock_cloud:
            parser = MagicMock()
            parser.files.create = AsyncMock()
            parser.parsing.parse = AsyncMock()
            mock_cloud.return_value = parser
            extractor = LlamaParseExtractor()
    return extractor


class TestLlamaParseExtractor:
    @pytest.mark.asyncio
    async def test_extract_returns_documents_with_filename_metadata(self):
        extractor = _make_extractor()
        extractor.parser.files.create.return_value = SimpleNamespace(id="file-1")
        extractor.parser.parsing.parse.return_value = SimpleNamespace(markdown=SimpleNamespace(pages=[SimpleNamespace(markdown="contenido")]))

        result = await extractor.extract(b"pdf content", "contrato.pdf")

        assert len(result) == 1
        assert result[0].metadata["filename"] == "contrato.pdf"
        assert result[0].metadata["page_number"] == 1

    @pytest.mark.asyncio
    async def test_extract_returns_multiple_documents(self):
        extractor = _make_extractor()
        extractor.parser.files.create.return_value = SimpleNamespace(id="file-1")
        extractor.parser.parsing.parse.return_value = SimpleNamespace(
            markdown=SimpleNamespace(pages=[SimpleNamespace(markdown="pagina 1"), SimpleNamespace(markdown="pagina 2")])
        )

        result = await extractor.extract(b"pdf content", "contrato.pdf")

        assert len(result) == 2
        assert result[0].metadata["total_pages"] == 2
        assert result[1].metadata["page_number"] == 2

    @pytest.mark.asyncio
    async def test_extract_parser_error_raises_extraction_error(self):
        extractor = _make_extractor()
        extractor.parser.files.create.return_value = SimpleNamespace(id="file-1")
        extractor.parser.parsing.parse.side_effect = Exception("API error")

        with pytest.raises(DocumentExtractionError, match="contrato.pdf"):
            await extractor.extract(b"pdf content", "contrato.pdf")

    @pytest.mark.asyncio
    async def test_extract_cleans_up_temp_file_on_success(self):
        extractor = _make_extractor()
        extractor.parser.files.create.return_value = SimpleNamespace(id="file-1")
        extractor.parser.parsing.parse.return_value = SimpleNamespace(markdown=SimpleNamespace(pages=[SimpleNamespace(markdown="contenido")]))

        with patch.object(Path, "unlink", autospec=True) as mock_unlink:
            await extractor.extract(b"content", "contrato.pdf")

        mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_cleans_up_temp_file_on_error(self):
        extractor = _make_extractor()
        extractor.parser.files.create.return_value = SimpleNamespace(id="file-1")
        extractor.parser.parsing.parse.side_effect = Exception("fail")

        with patch.object(Path, "unlink", autospec=True) as mock_unlink:
            with pytest.raises(DocumentExtractionError):
                await extractor.extract(b"content", "contrato.pdf")

        mock_unlink.assert_called_once()
