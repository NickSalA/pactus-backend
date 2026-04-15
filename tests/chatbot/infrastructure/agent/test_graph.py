"""Tests for the multi-node chatbot graph."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from contractai_backend.modules.chatbot.infrastructure.agent.access import ROLE_PERMISSION_DENIED_RESPONSE
from contractai_backend.modules.chatbot.infrastructure.agent.graph import ContractAgentGraph, DEFAULT_PERMISSION_DENIED_RESPONSE


def _make_graph(*, a1_route: str, a1_response: str | None, a3_response: str = "Respuesta del agente", permission_tools: list | None = None):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content=json.dumps({"route": a1_route, "response": a1_response}, ensure_ascii=True))])

    conversation_bound_llm = AsyncMock()
    conversation_bound_llm.ainvoke.return_value = AIMessage(content=a3_response)
    llm.bind_tools.return_value = conversation_bound_llm

    graph = ContractAgentGraph(tools=[], permission_tools=permission_tools or [], llm=llm).build_graph(checkpointer=None)
    return graph, llm.ainvoke, conversation_bound_llm.ainvoke


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
async def test_graph_uses_raw_a1_text_when_context_json_is_invalid() -> None:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Hola, puedo ayudarte con consultas sobre contratos."))

    bound_llm = AsyncMock()
    llm.bind_tools.return_value = bound_llm

    graph = ContractAgentGraph(tools=[], llm=llm).build_graph(checkpointer=None)
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="hola")],
            "user_context": {"organization_id": 1, "role": "WORKER"},
        }
    )

    assert result["messages"][-1].content == "Hola, puedo ayudarte con consultas sobre contratos."
    bound_llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_returns_n2_denial_for_invalid_role_context() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame el ranking de clientes")],
            "user_context": {"organization_id": 1, "role": "GUEST"},
        }
    )

    assert result["messages"][-1].content == DEFAULT_PERMISSION_DENIED_RESPONSE
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_calls_a3_for_allowed_information_requests() -> None:
    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        a3_response="Respuesta final",
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame el ranking de clientes")],
            "user_context": {"organization_id": 1, "role": "WORKER"},
        }
    )

    assert result["messages"][-1].content == "Respuesta final"
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_graph_denies_forbidden_document_scope_before_lookup() -> None:
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


@pytest.mark.asyncio
async def test_graph_denies_named_party_lookup_for_manager_with_deterministic_a2() -> None:
    @tool
    async def party_lookup_tool(party_name: str, limit: int = 5) -> str:
        """Returns a stored named-party match for permission tests."""
        return json.dumps(
            {
                "status": "success",
                "query": party_name,
                "matches": [
                    {
                        "document_id": 68,
                        "name": "Contrato Nick Salcedo",
                        "client": "Nick Emanuel Salcedo Alfaro",
                        "document_type": "LABOR",
                        "file_name": "contrato_nick_emanuel_salcedo_alfaro.pdf",
                        "match_score": 0.97,
                    }
                ],
                "matched_document_types": ["LABOR"],
                "match_count": 1,
            },
            ensure_ascii=True,
        )

    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        permission_tools=[party_lookup_tool],
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Hablame del contrato de Nick Salcedo")],
            "user_context": {"organization_id": 1, "role": "MANAGER", "allowed_document_types": ["COMPANY"]},
        }
    )

    assert result["messages"][-1].content == ROLE_PERMISSION_DENIED_RESPONSE
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_allows_named_party_lookup_for_hr_and_restricts_to_resolved_document() -> None:
    @tool
    async def party_lookup_tool(party_name: str, limit: int = 5) -> str:
        """Returns a stored named-party match for permission tests."""
        return json.dumps(
            {
                "status": "success",
                "query": party_name,
                "matches": [
                    {
                        "document_id": 68,
                        "name": "Contrato Nick Salcedo",
                        "client": "Nick Emanuel Salcedo Alfaro",
                        "document_type": "LABOR",
                        "file_name": "contrato_nick_emanuel_salcedo_alfaro.pdf",
                        "match_score": 0.97,
                    }
                ],
                "matched_document_types": ["LABOR"],
                "match_count": 1,
            },
            ensure_ascii=True,
        )

    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        a3_response="Respuesta final",
        permission_tools=[party_lookup_tool],
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Hablame del contrato de Nick Salcedo")],
            "user_context": {"organization_id": 1, "role": "HR", "allowed_document_types": ["LABOR"]},
        }
    )

    assert result["messages"][-1].content == "Respuesta final"
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_awaited_once()
    system_messages = conversation_ainvoke.await_args.args[0]
    assert any("document_ids=[68]" in message.content for message in system_messages if hasattr(message, "content"))


@pytest.mark.asyncio
async def test_graph_resolves_job_title_queries_to_named_labor_contract() -> None:
    @tool
    async def party_lookup_tool(party_name: str, limit: int = 5) -> str:
        """Returns a stored named-party match for job-title permission tests."""
        return json.dumps(
            {
                "status": "success",
                "query": party_name,
                "matches": [
                    {
                        "document_id": 68,
                        "name": "Contrato Estándar de Trabajador - Nick Salcedo",
                        "client": "Nick Emanuel Salcedo Alfaro",
                        "document_type": "LABOR",
                        "file_name": "contrato_nick_emanuel_salcedo_alfaro.pdf",
                        "match_score": 0.97,
                    }
                ],
                "matched_document_types": ["LABOR"],
                "match_count": 1,
            },
            ensure_ascii=True,
        )

    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        a3_response="El puesto es Analista.",
        permission_tools=[party_lookup_tool],
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Cual es el puesto de trabajo de Nick Salcedo?")],
            "user_context": {"organization_id": 1, "role": "HR", "allowed_document_types": ["LABOR"]},
        }
    )

    assert result["messages"][-1].content == "El puesto es Analista."
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_awaited_once()
    system_messages = conversation_ainvoke.await_args.args[0]
    assert any("document_ids=[68]" in message.content for message in system_messages if hasattr(message, "content"))


@pytest.mark.asyncio
async def test_graph_passes_explicit_state_to_named_party_lookup() -> None:
    captured_payloads: list[dict[str, object]] = []

    @tool
    async def party_lookup_tool(party_name: str, limit: int = 5, state: str | None = None) -> str:
        """Captures lookup payloads for permission tests."""
        captured_payloads.append({"party_name": party_name, "limit": limit, "state": state})
        return json.dumps(
            {"status": "no_match", "query": party_name, "matches": [], "matched_document_types": [], "match_count": 0}, ensure_ascii=True
        )

    graph, _, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        permission_tools=[party_lookup_tool],
    )

    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Hablame del contrato de Nick Salcedo, es borrador")],
            "user_context": {"organization_id": 1, "role": "HR", "allowed_document_types": ["LABOR"]},
        }
    )

    assert captured_payloads == [{"party_name": "nick salcedo", "limit": 10, "state": "DRAFT"}]
    conversation_ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_graph_clarifies_only_with_allowed_matches_when_lookup_is_ambiguous() -> None:
    @tool
    async def party_lookup_tool(party_name: str, limit: int = 5) -> str:
        """Returns mixed-scope matches for permission tests."""
        return json.dumps(
            {
                "status": "success",
                "query": party_name,
                "matches": [
                    {
                        "document_id": 10,
                        "name": "Contrato ACME Lima",
                        "client": "ACME Peru SAC",
                        "document_type": "COMPANY",
                        "file_name": "acme_lima.pdf",
                        "match_score": 0.95,
                    },
                    {
                        "document_id": 11,
                        "name": "Contrato ACME Arequipa",
                        "client": "ACME Peru SAC",
                        "document_type": "COMPANY",
                        "file_name": "acme_arequipa.pdf",
                        "match_score": 0.93,
                    },
                    {
                        "document_id": 12,
                        "name": "Contrato interno de ACME Worker",
                        "client": "ACME Worker",
                        "document_type": "LABOR",
                        "file_name": "acme_worker.pdf",
                        "match_score": 0.91,
                    },
                ],
                "matched_document_types": ["COMPANY", "LABOR"],
                "match_count": 3,
            },
            ensure_ascii=True,
        )

    graph, decision_ainvoke, conversation_ainvoke = _make_graph(
        a1_route="a2_permissions",
        a1_response=None,
        permission_tools=[party_lookup_tool],
    )

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Dame informacion del contrato de ACME")],
            "user_context": {"organization_id": 1, "role": "MANAGER", "allowed_document_types": ["COMPANY"]},
        }
    )

    response = result["messages"][-1].content
    assert "ACME Lima" in response
    assert "ACME Arequipa" in response
    assert "ACME Worker" not in response
    assert decision_ainvoke.await_count == 1
    conversation_ainvoke.assert_not_awaited()
