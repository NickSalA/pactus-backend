"""LLM factory for the chatbot agent."""

from collections.abc import Sequence

from langchain.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI

from .....shared.config import settings
from ...domain import LLMInitializationError


def get_llm() -> ChatGoogleGenerativeAI:
    """Build the chatbot LLM using Google Gemini."""
    try:
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            temperature=settings.MODEL_TEMPERATURE,
        )
    except Exception as e:
        raise LLMInitializationError(message=f"Fallo en credenciales o modelo: {e!s}") from e


def bind_tools_for_llm(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Bind tools with provider-specific options isolated from the graph."""
    return llm.bind_tools(list(tools))
