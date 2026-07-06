"""Módulo base para extractores de texto de documentos. Define la interfaz común que deben implementar los extractores específicos."""

from abc import ABC, abstractmethod


class DocumentExtractor(ABC):

    @abstractmethod
    async def extract(self, file: bytes, filename: str) -> list:
        """Extrae el texto de un documento dado su contenido en bytes y su nombre de archivo."""
        pass
