"""Tests for chatbot agent tools."""

import json
from unittest.mock import AsyncMock

import pytest

from pactus_backend.modules.chatbot.infrastructure.agent.tools import build_bc_tool, build_company_contracts_query_tool, build_party_lookup_tool
from pactus_backend.modules.documents.domain.value_objs import DocumentState
from pactus_backend.modules.users.domain.value_objs import UserRole


class _FakeCounterpartyRepo:
    def __init__(self, matches):
        self.search_contract_access_candidates = AsyncMock(return_value=matches)


class _FakeVectorRepo:
    def __init__(self):
        self.search_documents = AsyncMock(return_value="resultado")


class _FakeContractQueryService:
    def __init__(self):
        self.run_company_query = AsyncMock(return_value={"status": "success", "operation": "list", "items": []})


@pytest.mark.asyncio
async def test_party_lookup_tool_returns_document_types_from_repo_matches() -> None:
    repo = _FakeCounterpartyRepo(
        [
            {
                "document_id": 68,
                "name": "Contrato Nick Salcedo",
                "client": "Nick Emanuel Salcedo Alfaro",
                "document_type": "LABOR",
                "file_name": "contrato_nick_emanuel_salcedo_alfaro.pdf",
                "match_score": 0.97,
            }
        ]
    )
    tool = build_party_lookup_tool(repo=repo, organization_id=2)

    raw_result = await tool.ainvoke({"party_name": "Nick Salcedo", "limit": 5})
    result = json.loads(raw_result)

    assert result["status"] == "success"
    assert result["matched_document_types"] == ["LABOR"]
    assert result["matches"][0]["document_id"] == 68
    repo.search_contract_access_candidates.assert_awaited_once_with(
        organization_id=2,
        query="Nick Salcedo",
        limit=5,
        chatbot_ready_only=True,
        state=DocumentState.ACTIVE,
    )


@pytest.mark.asyncio
async def test_party_lookup_tool_returns_no_match_when_repo_finds_nothing() -> None:
    repo = _FakeCounterpartyRepo([])
    tool = build_party_lookup_tool(repo=repo, organization_id=2)

    raw_result = await tool.ainvoke({"party_name": "ACME", "limit": 5})
    result = json.loads(raw_result)

    assert result["status"] == "no_match"
    assert result["matches"] == []


@pytest.mark.asyncio
async def test_party_lookup_tool_respects_explicit_state() -> None:
    repo = _FakeCounterpartyRepo([])
    tool = build_party_lookup_tool(repo=repo, organization_id=2)

    await tool.ainvoke({"party_name": "ACME", "limit": 5, "state": DocumentState.DRAFT})

    repo.search_contract_access_candidates.assert_awaited_once_with(
        organization_id=2,
        query="ACME",
        limit=5,
        chatbot_ready_only=True,
        state=DocumentState.DRAFT,
    )


@pytest.mark.asyncio
async def test_bc_tool_uses_active_scope_by_default() -> None:
    repo = _FakeVectorRepo()
    tool = build_bc_tool(
        repo=repo,
        user_role=UserRole.WORKER,
        allowed_document_ids={1},
        document_ids_by_state={DocumentState.ACTIVE: {1}, DocumentState.DRAFT: {2}},
    )

    await tool.ainvoke({"query": "resumen del contrato", "limit": 5})

    repo.search_documents.assert_awaited_once_with(query="resumen del contrato", limit=5, document_ids=[1])


@pytest.mark.asyncio
async def test_bc_tool_uses_explicit_state_scope_when_requested() -> None:
    repo = _FakeVectorRepo()
    tool = build_bc_tool(
        repo=repo,
        user_role=UserRole.WORKER,
        allowed_document_ids={1},
        document_ids_by_state={DocumentState.ACTIVE: {1}, DocumentState.DRAFT: {2}},
    )

    await tool.ainvoke({"query": "resumen del contrato borrador", "limit": 5})

    repo.search_documents.assert_awaited_once_with(query="resumen del contrato borrador", limit=5, document_ids=[2])


@pytest.mark.asyncio
async def test_company_contracts_query_tool_forwards_service_filters() -> None:
    service = _FakeContractQueryService()
    tool = build_company_contracts_query_tool(service=service, organization_id=2)

    raw_result = await tool.ainvoke(
        {
            "operation": "list",
            "service_name": "Hosting",
            "service_id": 5,
            "limit": 3,
        }
    )
    result = json.loads(raw_result)

    assert result["status"] == "success"
    service.run_company_query.assert_awaited_once()
    awaited_kwargs = service.run_company_query.await_args.kwargs
    assert awaited_kwargs["organization_id"] == 2
    assert awaited_kwargs["query"].service_name == "Hosting"
    assert awaited_kwargs["query"].service_id == 5
    assert awaited_kwargs["query"].limit == 3
