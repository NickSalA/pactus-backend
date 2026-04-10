"""Repository interface for invoking the Large Language Model (LLM) provider."""

from abc import ABC, abstractmethod
from typing import Any


class ILLMProvider(ABC):
    @abstractmethod
    async def invoke(self, message: str, thread_id: int, user_context: dict[str, Any]) -> tuple[str, int]:
        """Invokes the LLM provider with the given message and mandatory thread ID."""
        pass
