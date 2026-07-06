"""Tests for chatbot Qdrant retrieval filters and formatting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pactus_backend.modules.chatbot.infrastructure.qdrant_repo import QdrantVectorRepository


def _make_repo(organization_id: int = 7) -> tuple[QdrantVectorRepository, AsyncMock]:
    client = AsyncMock()
    repo = QdrantVectorRepository(
        collection_names=["contracts_index", "drive_contracts_index"],
        client=client,
        organization_id=organization_id,
    )
    return repo, client


class TestBuildFilters:
    def test_build_filters_always_include_organization(self):
        repo, _ = _make_repo(organization_id=15)

        filters = repo._build_filters()

        assert len(filters.filters) == 1
        assert filters.filters[0].key == "organization_id"
        assert filters.filters[0].value == "15"

    def test_build_filters_include_document_ids_when_present(self):
        repo, _ = _make_repo()

        filters = repo._build_filters(document_ids=[3, 9])

        assert len(filters.filters) == 2
        assert filters.filters[1].key == "document_id"
        assert filters.filters[1].value == ["3", "9"]


class TestRetrieveFromCollection:
    @pytest.mark.asyncio
    async def test_retriever_receives_metadata_filters(self):
        repo, client = _make_repo()
        client.collection_exists.return_value = True

        retriever = AsyncMock()
        retriever.aretrieve.return_value = []
        index = MagicMock()
        index.as_retriever.return_value = retriever

        with patch("pactus_backend.modules.chatbot.infrastructure.qdrant_repo.VectorStoreIndex.from_vector_store", return_value=index):
            await repo._retrieve_from_collection(
                collection_name="contracts_index",
                query="firmantes del contrato alpha",
                limit=4,
                document_ids=[10],
            )

        filters = index.as_retriever.call_args.kwargs["filters"]
        assert filters.filters[0].key == "organization_id"
        assert filters.filters[0].value == "7"
        assert filters.filters[1].key == "document_id"
        assert filters.filters[1].value == ["10"]


class TestSearchDocuments:
    @pytest.mark.asyncio
    async def test_formats_document_identifier_in_sources(self):
        repo, _ = _make_repo()
        node = MagicMock()
        node.score = 0.95
        node.metadata = {"filename": "Contrato Alpha.pdf", "document_id": "42"}
        node.text = "Firmado por Juan Perez."

        with patch.object(repo, "_retrieve_from_collection", new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.side_effect = [[node], []]
            with patch(
                "pactus_backend.modules.chatbot.infrastructure.qdrant_repo.MetadataReplacementPostProcessor.postprocess_nodes",
                return_value=[node],
            ):
                result = await repo.search_documents(query="firmantes", limit=5, document_ids=[42])

        assert "Fuente: Contrato Alpha.pdf | Documento: 42" in result
        assert "Firmado por Juan Perez." in result
