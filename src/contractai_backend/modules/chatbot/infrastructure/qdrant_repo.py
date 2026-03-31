"""Reposity of vectors for Qdrant, using LlamaIndex to manage the index and retrieval logic."""

from typing import Any

from llama_index.core import QueryBundle, VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.postprocessor import MetadataReplacementPostProcessor
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import FilterCondition, FilterOperator, MetadataFilter, MetadataFilters
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient

from ..application.repositories import VectorRepository
from ..domain import VectorDatabaseUnavailableError, VectorSearchError


class QdrantVectorRepository(VectorRepository):
    def __init__(self, collection_names: list[str], client: AsyncQdrantClient, organization_id: int):
        self.client: AsyncQdrantClient = client
        self.collection_names: list[str] = collection_names
        self.organization_id: int = organization_id

    @classmethod
    async def build(cls, client: AsyncQdrantClient, collection_names: list[str], organization_id: int) -> "QdrantVectorRepository":
        """Factory method para construir el repositorio, asegurando la creación del índice y la colección en Qdrant."""
        try:
            normalized_names = list(dict.fromkeys(name for name in collection_names if name))
            return cls(collection_names=normalized_names, client=client, organization_id=organization_id)
        except Exception as e:
            raise VectorDatabaseUnavailableError(message=f"No se pudo conectar con Qdrant: {e!s}") from e

    def _build_filters(self, document_ids: list[int] | None = None) -> MetadataFilters:
        filters = [MetadataFilter(key="organization_id", value=str(self.organization_id), operator=FilterOperator.EQ)]

        if document_ids:
            filters.append(
                MetadataFilter(
                    key="document_id",
                    value=[str(document_id) for document_id in document_ids],
                    operator=FilterOperator.IN,
                )
            )

        return MetadataFilters(filters=filters, condition=FilterCondition.AND)

    async def _retrieve_from_collection(
        self,
        collection_name: str,
        query: str,
        limit: int,
        document_ids: list[int] | None = None,
    ) -> list[NodeWithScore]:
        exists = await self.client.collection_exists(collection_name=collection_name)
        if not exists:
            return []

        vector_store = QdrantVectorStore(aclient=self.client, collection_name=collection_name)
        index: VectorStoreIndex = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        retriever: BaseRetriever = index.as_retriever(
            similarity_top_k=limit,
            filters=self._build_filters(document_ids=document_ids),
        )
        return await retriever.aretrieve(str_or_query_bundle=query)

    async def search_documents(self, query: str, limit: int = 5, document_ids: list[int] | None = None) -> str:
        """Busca documentos relevantes en Qdrant usando el retriever de LlamaIndex y devuelve un string formateado."""
        try:
            nodes: list[NodeWithScore] = []
            for collection_name in self.collection_names:
                nodes.extend(
                    await self._retrieve_from_collection(
                        collection_name=collection_name,
                        query=query,
                        limit=limit,
                        document_ids=document_ids,
                    )
                )

            nodes.sort(key=lambda node: node.score or 0.0, reverse=True)
            nodes = nodes[:limit]

            if not nodes:
                return ""

            processor = MetadataReplacementPostProcessor(target_metadata_key="window")
            new_nodes: list[NodeWithScore] = processor.postprocess_nodes(nodes, query_bundle=QueryBundle(query))
        except Exception as e:
            raise VectorSearchError(message=f"Fallo en el retriever de LlamaIndex: {e!s}") from e

        contextos_formateados: list[str] = []
        for node in new_nodes:
            filename: Any = node.metadata.get("filename", "Desconocido")
            document_id: Any = node.metadata.get("document_id", "Desconocido")
            texto: str = node.text
            contextos_formateados.append(f"[Fuente: {filename} | Documento: {document_id}]\n{texto}")

        return "\n\n---\n\n".join(contextos_formateados)
