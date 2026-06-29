"""Vector Database Management to Qdrant."""

from qdrant_client import AsyncQdrantClient, QdrantClient

from ...config import settings


async def get_aclient() -> AsyncQdrantClient:
    """Obtiene una instancia del cliente asíncrono de Qdrant."""
    return AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def get_client() -> QdrantClient:
    """Obtiene una instancia del cliente síncrono de Qdrant."""
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
