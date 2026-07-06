"""Configuración de Voyage AI para LlamaIndex."""

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding

from ....shared.config import settings
from ..domain.exceptions import DocumentVectorError


# TODO: Cambiar en el futuro al modelo de embedding de Voyage AI una vez que esté disponible públicamente.
def configure_embedding() -> None:
    """Configura el modelo de embedding de Voyage AI globalmente para LlamaIndex."""
    try:
        Settings.embed_model = OpenAIEmbedding(
            model_name=settings.OPENAI_EMBEDDING_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
            embed_batch_size=50,
            dimensions=1536,
        )
    except Exception as e:
        raise DocumentVectorError(f"Error al configurar modelo de embeddings: {e!s}") from e
