"""Tests unitarios para LlamaIndexQdrantRepository con clientes Qdrant mockeados."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pactus_backend.modules.documents.domain.exceptions import DocumentVectorError, DocumentVectorUnavailableError
from pactus_backend.modules.documents.infrastructure.qdrant_repo import LlamaIndexQdrantRepository


def _make_repo() -> tuple[LlamaIndexQdrantRepository, AsyncMock, MagicMock]:
    async_client = AsyncMock()
    sync_client = MagicMock()
    repo = LlamaIndexQdrantRepository(async_client=async_client, sync_client=sync_client)
    return repo, async_client, sync_client


def _make_chunk(id_: str = "chunk_0") -> MagicMock:
    chunk = MagicMock()
    chunk.id_ = id_
    chunk.relationships = {}
    chunk.metadata = {}
    chunk.excluded_embed_metadata_keys = []
    chunk.excluded_llm_metadata_keys = []
    return chunk


# ---------------------------------------------------------------------------
# delete_vectors
# ---------------------------------------------------------------------------


class TestDeleteVectors:
    @pytest.mark.asyncio
    async def test_deletes_vectors_when_collection_exists(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = True

        await repo.delete_vectors("contracts_index", document_id=1)

        async_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_delete_when_collection_not_exists(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = False

        await repo.delete_vectors("contracts_index", document_id=1)

        async_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_raises_vector_unavailable(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.side_effect = Exception("network error")

        with pytest.raises(DocumentVectorUnavailableError):
            await repo.delete_vectors("contracts_index", document_id=1)


# ---------------------------------------------------------------------------
# _ensure_collection
# ---------------------------------------------------------------------------


class TestEnsureCollection:
    @pytest.mark.asyncio
    async def test_creates_collection_when_not_exists(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = False

        await repo._ensure_collection("contracts_index")

        async_client.recreate_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_creation_when_collection_exists(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = True

        await repo._ensure_collection("contracts_index")

        async_client.recreate_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_payload_indexes_needed_by_admin_and_vector_filters(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = True

        await repo._ensure_collection("contracts_index")

        indexed_fields = [call.kwargs["field_name"] for call in async_client.create_payload_index.await_args_list]
        assert indexed_fields == ["filename", "document_id", "organization_id", "source_provider", "source_file_id"]

    @pytest.mark.asyncio
    async def test_ignores_already_exists_error_on_payload_index(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = True
        async_client.create_payload_index.side_effect = Exception("already exists")

        # no debe lanzar
        await repo._ensure_collection("contracts_index")

    @pytest.mark.asyncio
    async def test_raises_vector_error_on_unexpected_payload_index_error(self):
        repo, async_client, _ = _make_repo()
        async_client.collection_exists.return_value = True
        async_client.create_payload_index.side_effect = Exception("unexpected failure")

        with pytest.raises(DocumentVectorError):
            await repo._ensure_collection("contracts_index")


# ---------------------------------------------------------------------------
# add_vectors
# ---------------------------------------------------------------------------


class TestAddVectors:
    @pytest.mark.asyncio
    async def test_add_vectors_sets_chunk_metadata(self):
        repo, async_client, sync_client = _make_repo()
        async_client.collection_exists.return_value = True

        chunk = _make_chunk()
        chunks = [chunk]

        with patch("pactus_backend.modules.documents.infrastructure.qdrant_repo.run_in_threadpool", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock()
            await repo.add_vectors("contracts_index", document_id=42, chunks=chunks)

        assert chunk.metadata["document_id"] == "42"
        assert chunk.id_ == "42_chunk_0"

    @pytest.mark.asyncio
    async def test_add_vectors_calls_delete_first(self):
        repo, async_client, sync_client = _make_repo()
        async_client.collection_exists.return_value = True

        with patch("pactus_backend.modules.documents.infrastructure.qdrant_repo.run_in_threadpool", new_callable=AsyncMock):
            await repo.add_vectors("contracts_index", document_id=1, chunks=[_make_chunk()])

        # delete_vectors llama a async_client.delete
        async_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_vectors_threadpool_error_raises_vector_error(self):
        repo, async_client, sync_client = _make_repo()
        async_client.collection_exists.return_value = True

        with patch(
            "pactus_backend.modules.documents.infrastructure.qdrant_repo.run_in_threadpool",
            new_callable=AsyncMock,
            side_effect=Exception("embedding failed"),
        ):
            with pytest.raises(DocumentVectorError):
                await repo.add_vectors("contracts_index", document_id=1, chunks=[_make_chunk()])

    @pytest.mark.asyncio
    async def test_add_vectors_keeps_sync_client_open_for_batch_reuse(self):
        repo, async_client, sync_client = _make_repo()
        async_client.collection_exists.return_value = True

        with patch("pactus_backend.modules.documents.infrastructure.qdrant_repo.run_in_threadpool", new_callable=AsyncMock):
            await repo.add_vectors("contracts_index", document_id=1, chunks=[_make_chunk()])
            await repo.add_vectors("contracts_index", document_id=2, chunks=[_make_chunk()])

        sync_client.close.assert_not_called()
