"""Definición de la interfaz del repositorio de generación de documentos."""

from abc import ABC, abstractmethod


class IDocumentGenerator(ABC):
    @abstractmethod
    async def generate_pdf(self, markdown_content: str) -> bytes:
        """Toma el Markdown ya inyectado y el nombre de archivo deseado. Genera el PDF y retorna la ruta o URL donde se guardó."""
        pass
