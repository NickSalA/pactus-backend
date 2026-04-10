from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph, RunnableConfig

from contractai_backend.modules.chatbot.application.repositories import ILLMProvider
from contractai_backend.modules.chatbot.domain import LLMExecutionError, LLMQuotaExceededError


class LangGraphLLMAdapter(ILLMProvider):
    def __init__(self, compiled_graph: CompiledStateGraph):
        self.graph = compiled_graph

    async def invoke(self, message: str, thread_id: int, user_context: dict[str, Any]) -> tuple[str, int]:
        config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}

        try:
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=message)], "user_context": user_context},
                config=config,
            )
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMQuotaExceededError()
            raise LLMExecutionError(message=f"Error en la malla de LangGraph: {str(e)}")

        last_message = result["messages"][-1]
        raw_content = last_message.content

        if isinstance(raw_content, list):
            output_message = "".join([part.get("text", "") for part in raw_content if isinstance(part, dict) and "text" in part])
        else:
            output_message = str(raw_content)

        input_tokens = 0
        output_tokens = 0

        if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
            input_tokens = last_message.usage_metadata.get("input_tokens", 0)
            output_tokens = last_message.usage_metadata.get("output_tokens", 0)

        output_message += f"\n\n---\n📊 Tokens de entrada: {input_tokens} | Tokens de salida: {output_tokens}"

        return output_message, thread_id
