import json
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph, RunnableConfig

from contractai_backend.modules.chatbot.application.dto import ChartData, LLMResult
from contractai_backend.modules.chatbot.application.repositories.base_llm import ILLMProvider
from contractai_backend.modules.chatbot.domain import LLMExecutionError, LLMQuotaExceededError
from contractai_backend.shared.config import settings

_CHART_TOOL_NAME = "dashboard_chart_tool"


class LangGraphLLMAdapter(ILLMProvider):
    def __init__(self, compiled_graph: CompiledStateGraph):
        self.graph = compiled_graph

    async def invoke(self, message: str, thread_id: int, user_context: dict[str, Any]) -> LLMResult:
        config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}

        try:
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=message)], "user_context": user_context},
                config=config,
            )
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMQuotaExceededError() from e
            raise LLMExecutionError(message=f"Error en la malla de LangGraph: {e!s}") from e

        last_message = result["messages"][-1]
        raw_content = last_message.content

        if isinstance(raw_content, list):
            output_message = "".join([part.get("text", "") for part in raw_content if isinstance(part, dict) and "text" in part])
        else:
            output_message = str(raw_content)

        input_tokens = 0
        output_tokens = 0
        model_used = settings.GEMINI_MODEL_NAME

        if hasattr(last_message, "usage_metadata") and last_message.usage_metadata:
            input_tokens = last_message.usage_metadata.get("input_tokens", 0)
            output_tokens = last_message.usage_metadata.get("output_tokens", 0)

        chart_data = self._extract_chart_from_messages(result["messages"])

        return LLMResult(
            response=output_message,
            thread_id=thread_id,
            chart=chart_data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model_used=model_used,
        )

    @staticmethod
    def _extract_chart_from_messages(messages: list[BaseMessage]) -> ChartData | None:
        """Walk messages in reverse looking for a successful dashboard_chart_tool call."""
        for msg in reversed(messages):
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name != _CHART_TOOL_NAME:
                continue

            try:
                payload = json.loads(str(msg.content))
            except (json.JSONDecodeError, TypeError):
                continue

            if payload.get("status") != "success":
                continue

            chart_raw = payload.get("chart")
            if chart_raw is None:
                continue

            try:
                return ChartData.model_validate(chart_raw)
            except Exception:
                continue

        return None
