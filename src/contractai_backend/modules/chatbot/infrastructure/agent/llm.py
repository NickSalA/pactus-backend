"""LLM factory for the chatbot agent."""

from collections.abc import Sequence

from langchain.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ...domain import LLMInitializationError
from .....shared.config import settings


def get_llm() -> ChatOpenAI:
    """Build the chatbot LLM using OpenAI GPT."""
    try:
        return ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.MODEL_TEMPERATURE,
            max_retries=1,
            timeout=20,
        )
    except Exception as e:
        raise LLMInitializationError(message=f"Fallo en credenciales o modelo: {str(e)}") from e


def bind_tools_for_llm(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Bind tools with provider-specific options isolated from the graph."""
    return llm.bind_tools(list(tools), parallel_tool_calls=False)
