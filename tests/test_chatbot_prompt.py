"""Tests for chatbot prompt routing rules."""

from contractai_backend.modules.chatbot.infrastructure.agent.prompts import (
    get_context_agent_prompt,
    get_conversation_agent_prompt,
    get_permission_agent_prompt,
)


def test_context_prompt_defines_a1_json_routes() -> None:
    prompt = get_context_agent_prompt()

    assert "You are A1" in prompt
    assert "n1_early_response" in prompt
    assert "a2_permissions" in prompt
    assert "Return ONLY JSON" in prompt


def test_permission_prompt_defines_a2_json_routes() -> None:
    prompt = get_permission_agent_prompt()

    assert "You are A2" in prompt
    assert "trusted backend user context" in prompt
    assert "party_lookup_tool" in prompt
    assert "ADMIN, HR, MANAGER, WORKER" in prompt
    assert "a3_conversation" in prompt
    assert "n2_denied_response" in prompt
    assert "HR can access only LABOR" in prompt
    assert "No tienes permisos para acceder a esa informacion." in prompt


def test_conversation_prompt_includes_tool_routing_rules() -> None:
    prompt = get_conversation_agent_prompt()

    assert "currently_active=true" in prompt
    assert "start_date <= today <= end_date" in prompt
    assert "contracts with a specific service" in prompt
    assert "service_name or service_id" in prompt
    assert "which services are attached to a contract" in prompt
    assert "document_ids" in prompt
    assert "### Ranking de clientes" in prompt
    assert 'If the user asks for a contract "with" or "signed by" a person name' in prompt
    assert "Do not apply the counterparty rule when the named entity looks like a person" in prompt
    assert "If the tool returns forbidden" in prompt
    assert "No tienes permisos para acceder a esa informacion." in prompt
