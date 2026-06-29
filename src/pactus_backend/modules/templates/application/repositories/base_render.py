"""Definición de la interfaz del repositorio de renderizado de plantillas."""

from abc import ABC, abstractmethod
from typing import Any


class ITemplateRenderer(ABC):
    @abstractmethod
    async def render(self, template_md: str, payload: dict[str, Any]) -> str:
        """Toma el molde (Markdown con llaves) y el diccionario de datos. Retorna el Markdown final inyectado."""
        pass
