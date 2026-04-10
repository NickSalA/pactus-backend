"""Graph definition for the ContractAI chatbot agent."""

import json
from functools import partial

from langchain.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .access import ROLE_PERMISSION_DENIED_RESPONSE, evaluate_document_access
from .decisions import ContextAgentDecision, PermissionAgentDecision, parse_structured_decision
from .llm import bind_tools_for_llm
from .prompts import get_context_agent_prompt, get_conversation_agent_prompt, get_permission_agent_prompt
from .state import AgentState

DEFAULT_EARLY_RESPONSE = (
    "Puedo ayudarte con consultas informativas sobre contratos y documentos. "
    "En este chat no ejecuto acciones ni modificaciones; solo respondo consultas y rankings con la informacion disponible."
)
DEFAULT_PERMISSION_DENIED_RESPONSE = (
    "No tengo un contexto de permisos valido para atender esta consulta. Por favor vuelve a iniciar sesion o contacta a un administrador."
)


def _extract_latest_user_message(state: AgentState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""

    latest_message = messages[-1]
    if isinstance(latest_message, BaseMessage):
        content = latest_message.content
    elif isinstance(latest_message, dict):
        content = latest_message.get("content", "")
    else:
        content = getattr(latest_message, "content", "")

    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))

    return str(content)


async def _invoke_agent(llm: BaseChatModel | Runnable, system_prompt: str, payload: dict[str, object]):
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(payload, ensure_ascii=True)),
    ]
    return await llm.ainvoke(messages)


async def run_context_agent(state: AgentState, llm: BaseChatModel):
    """A1: classify the request with a dedicated LLM agent."""
    message = _extract_latest_user_message(state)
    response = await _invoke_agent(
        llm=llm,
        system_prompt=get_context_agent_prompt(),
        payload={"user_message": message},
    )

    try:
        decision = parse_structured_decision(response.content, ContextAgentDecision)
    except Exception:
        return {"context_route": "n1_early_response", "early_response": DEFAULT_EARLY_RESPONSE}

    return {
        "context_route": decision.route,
        "early_response": decision.response if decision.route == "n1_early_response" else None,
    }


def route_after_context(state: AgentState) -> str:
    return state.get("context_route", "a2_permissions")


async def run_permission_agent(state: AgentState, llm: BaseChatModel):
    """A2: validate trusted backend permissions with a dedicated LLM agent."""
    message = _extract_latest_user_message(state)
    user_context = state.get("user_context") or {}
    access_decision = evaluate_document_access(message=message, user_role=user_context.get("role"))
    if access_decision.is_denied:
        return {
            "permission_route": "n2_denied_response",
            "permission_response": ROLE_PERMISSION_DENIED_RESPONSE,
        }

    response = await _invoke_agent(
        llm=llm,
        system_prompt=get_permission_agent_prompt(),
        payload={
            "user_message": message,
            "trusted_user_context": user_context,
            "access_policy_hint": access_decision.to_prompt_payload(),
        },
    )

    try:
        decision = parse_structured_decision(response.content, PermissionAgentDecision)
    except Exception:
        return {
            "permission_route": "n2_denied_response",
            "permission_response": DEFAULT_PERMISSION_DENIED_RESPONSE,
        }

    return {
        "permission_route": decision.route,
        "permission_response": decision.response if decision.route == "n2_denied_response" else None,
    }


def route_after_permissions(state: AgentState) -> str:
    return state.get("permission_route", "n2_denied_response")


def route_after_conversation(state: AgentState) -> str:
    """Route A3 either to tools or to the final response node."""
    messages = state.get("messages", [])
    if not messages:
        return "n3_final_response"

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    return "tools" if tool_calls else "n3_final_response"


def build_terminal_response(state_key: str):
    def respond(state: AgentState):
        message = state.get(state_key) or ""
        return {"messages": [AIMessage(content=message)]}

    return respond


async def call_model(state: AgentState, llm: Runnable):
    """A3: run the conversational agent with tool access."""
    system_message = SystemMessage(content=get_conversation_agent_prompt())
    user_context = state.get("user_context") or {}
    allowed_document_types = user_context.get("allowed_document_types")
    access_scope = "all document types" if allowed_document_types is None else ", ".join(allowed_document_types)
    access_message = SystemMessage(
        content=(
            "Trusted backend access scope: "
            f"role={user_context.get('role')} | allowed_document_types={access_scope}. "
            f"If the user explicitly requests a document type outside that scope, respond exactly with: '{ROLE_PERMISSION_DENIED_RESPONSE}'. "
            f"If any tool returns status='forbidden' or the exact message '{ROLE_PERMISSION_DENIED_RESPONSE}', respond exactly with that same message."
        )
    )
    messages = [system_message, access_message] + state["messages"]

    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def finalize_response(_: AgentState):
    """N3: explicit final response node."""
    return {}


class ContractAgentGraph:
    def __init__(self, tools: list, llm: BaseChatModel):
        self.tools = tools
        self.decision_llm = llm
        self.conversation_llm = bind_tools_for_llm(llm, self.tools)

    def build_graph(self, checkpointer):
        """Build the multi-node chatbot graph."""
        workflow = StateGraph(AgentState)  # ty:ignore[invalid-argument-type]
        context_node = partial(run_context_agent, llm=self.decision_llm)
        permission_node = partial(run_permission_agent, llm=self.decision_llm)
        agent_node = partial(call_model, llm=self.conversation_llm)

        workflow.add_node("a1_context", context_node)
        workflow.add_node("a2_permissions", permission_node)
        workflow.add_node("a3_conversation", agent_node)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("n1_early_response", build_terminal_response("early_response"))
        workflow.add_node("n2_denied_response", build_terminal_response("permission_response"))
        workflow.add_node("n3_final_response", finalize_response)

        workflow.add_edge(START, "a1_context")
        workflow.add_conditional_edges(
            "a1_context",
            route_after_context,
            {
                "a2_permissions": "a2_permissions",
                "n1_early_response": "n1_early_response",
            },
        )
        workflow.add_conditional_edges(
            "a2_permissions",
            route_after_permissions,
            {
                "a3_conversation": "a3_conversation",
                "n2_denied_response": "n2_denied_response",
            },
        )
        workflow.add_conditional_edges(
            "a3_conversation",
            route_after_conversation,
            {
                "tools": "tools",
                "n3_final_response": "n3_final_response",
            },
        )
        workflow.add_edge("tools", "a3_conversation")
        workflow.add_edge("n1_early_response", END)
        workflow.add_edge("n2_denied_response", END)
        workflow.add_edge("n3_final_response", END)

        return workflow.compile(checkpointer=checkpointer)
