"""LLM factory for the chatbot agent."""

from collections.abc import Sequence

from langchain.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_openai import AzureChatOpenAI

from .....shared.config import settings
from ...domain import LLMInitializationError


def get_llm() -> AzureChatOpenAI:
    """Build the chatbot LLM using OpenAI GPT."""
    try:
        return AzureChatOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            temperature=settings.MODEL_TEMPERATURE,
            azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        )
    except Exception as e:
        raise LLMInitializationError(message=f"Fallo en credenciales o modelo: {e!s}") from e


def bind_tools_for_llm(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Bind tools with provider-specific options isolated from the graph."""
    return llm.bind_tools(list(tools), parallel_tool_calls=False)
