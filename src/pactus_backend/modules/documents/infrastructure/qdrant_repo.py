"""Repository implementation for managing document vectors in Qdrant, integrated with LlamaIndex for vector storage and retrieval."""

from fastapi.concurrency import run_in_threadpool
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http import models

from ..application.repositories import VectorRepository
from ..domain.exceptions import DocumentVectorError, DocumentVectorUnavailableError


class LlamaIndexQdrantRepository(VectorRepository):
    def __init__(self, async_client: AsyncQdrantClient, sync_client: QdrantClient):
        self.async_client: AsyncQdrantClient = async_client
        self.sync_client: QdrantClient = sync_client

    def _get_node_parser(self):
        """Configura el NodeParser de LlamaIndex para dividir el texto en ventanas de 3 oraciones."""
        return SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

    async def _ensure_collection(self, index: str):
        """Asegura que la colección de documentos exista en Qdrant."""
        exists: bool = await self.async_client.collection_exists(collection_name=index)
        if not exists:
            await self.async_client.recreate_collection(
                collection_name=index, vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE)
            )
        try:
            await self.async_client.create_payload_index(collection_name=index, field_name="filename", field_schema=models.PayloadSchemaType.KEYWORD)
        except Exception as e:
            if "already exists" not in str(object=e):
                raise DocumentVectorError(f"No se pudo indexar el campo filename: {e!s}") from e

        try:
            await self.async_client.create_payload_index(
                collection_name=index,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(object=e):
                raise DocumentVectorError(f"No se pudo indexar el campo document_id: {e!s}") from e

        for field_name in ["organization_id", "source_provider", "source_file_id"]:
            try:
                await self.async_client.create_payload_index(
                    collection_name=index,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                if "already exists" not in str(object=e):
                    raise DocumentVectorError(f"No se pudo indexar el campo {field_name}: {e!s}") from e

    async def delete_vectors(self, index_name: str, document_id: int):
        """Elimina todos los vectores asociados a un documento específico en Qdrant, identificados por el nombre del archivo."""
        try:
            exists: bool = await self.async_client.collection_exists(collection_name=index_name)
            if not exists:
                return

            await self.async_client.delete(
                collection_name=index_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(object=document_id)))])
                ),
            )
        except Exception as e:
            raise DocumentVectorUnavailableError("Ocurrió un error de red al intentar eliminar los vectores del documento.") from e

    async def add_vectors(self, index_name: str, document_id: int, chunks: list) -> None:
        """Ejecuta la ingesta de LlamaIndex hacia Qdrant."""
        await self._ensure_collection(index=index_name)

        for i, chunk in enumerate(iterable=chunks):
            chunk.id_ = f"{document_id}_chunk_{i}"
            chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=str(object=document_id))
            chunk.metadata["document_id"] = str(object=document_id)
            chunk.excluded_embed_metadata_keys: list[str] = ["document_id"]
            chunk.excluded_llm_metadata_keys: list[str] = ["document_id"]

        await self.delete_vectors(index_name, document_id)

        vector_store: QdrantVectorStore = QdrantVectorStore(client=self.sync_client, collection_name=index_name)
        storage_context: StorageContext = StorageContext.from_defaults(vector_store=vector_store)

        try:
            await run_in_threadpool(
                func=lambda: VectorStoreIndex.from_documents(
                    documents=chunks,
                    storage_context=storage_context,
                    node_parser=self._get_node_parser(),
                    show_progress=True,
                )
            )
        except Exception as e:
            raise DocumentVectorError("Fallo el procesamiento matemático o la inserción de los vectores.") from e
