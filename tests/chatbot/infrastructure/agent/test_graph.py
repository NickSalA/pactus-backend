"""Tests for the multi-node chatbot graph."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from contractai_backend.modules.chatbot.infrastructure.agent.access import ROLE_PERMISSION_DENIED_RESPONSE
from contractai_backend.modules.chatbot.infrastructure.agent.graph import ContractAgentGraph
from contractai_backend.modules.chatbot.infrastructure.agent.graph import DEFAULT_PERMISSION_DENIED_RESPONSE


def _make_graph(
    *,
    a1_route: str,
    a1_response: str | None,
    a2_route: str = "a3_conversation",
    a2_response: str | None = None,
    a3_response: str = "Respuesta del agente",
):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=json.dumps({"route": a1_route, "response": a1_response}, ensure_ascii=True)),
            AIMessage(content=json.dumps({"route": a2_route, "response": a2_response}, ensure_ascii=True)),
        ]
    )

    bound_llm = AsyncMock()
    bound_llm.ainvoke.return_value = AIMessage(content=a3_response)
    llm.bind_tools.return_value = bound_llm

    graph = ContractAgentGraph(tools=[], llm=llm).build_graph(checkpointer=None)
    return graph, llm.ainvoke, bound_llm.ainvoke


@pytest.mark.asyncio
async def test_graph_returns_n1_early_response_from_a1() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="n1_early_response",
        a1_response="Hola. Puedo ayudarte con consultas sobre contratos, rankings y contenido documental.",
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Hola")],
            "user_context": {"organization_id": 1, "role": "WORKER"},
        }
    )

    assert result["messages"][-1].content == "Hola. Puedo ayudarte con consultas sobre contratos, rankings y contenido documental."
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_returns_n2_denial_from_a2() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        a2_route="n2_denied_response",
        a2_response=DEFAULT_PERMISSION_DENIED_RESPONSE,
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame el ranking de clientes")],
            "user_context": {"organization_id": 1, "role": "GUEST"},
        }
    )

    assert result["messages"][-1].content == DEFAULT_PERMISSION_DENIED_RESPONSE
    assert decision_ainvoke.await_count == 2
    conversation_ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_calls_a3_for_allowed_information_requests() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        a2_route="a3_conversation",
        a2_response=None,
        a3_response="Respuesta final",
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame el ranking de clientes")],
            "user_context": {"organization_id": 1, "role": "WORKER"},
        }
    )

    assert result["messages"][-1].content == "Respuesta final"
    assert decision_ainvoke.await_count == 2
    conversation_ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_graph_denies_forbidden_document_scope_before_a2_llm() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame contratos con empresas")],
            "user_context": {"organization_id": 1, "role": "HR", "allowed_document_types": ["LABOR"]},
        }
    )

    assert result["messages"][-1].content == ROLE_PERMISSION_DENIED_RESPONSE
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_not_awaited()
