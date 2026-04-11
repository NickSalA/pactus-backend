"""Tests for chatbot agent tools."""

import json
from unittest.mock import AsyncMock

import pytest

from contractai_backend.modules.chatbot.infrastructure.agent.tools import build_party_lookup_tool


class _FakeCounterpartyRepo:
    def __init__(self, matches):
        self.search_contract_access_candidates = AsyncMock(return_value=matches)


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
    repo.search_contract_access_candidates.assert_awaited_once_with(organization_id=2, query="Nick Salcedo", limit=5)


@pytest.mark.asyncio
async def test_party_lookup_tool_returns_no_match_when_repo_finds_nothing() -> None:
    repo = _FakeCounterpartyRepo([])
    tool = build_party_lookup_tool(repo=repo, organization_id=2)

    raw_result = await tool.ainvoke({"party_name": "ACME", "limit": 5})
    result = json.loads(raw_result)

    assert result["status"] == "no_match"
    assert result["matches"] == []
