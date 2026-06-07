"""Unit-level tests for dashboard repository helpers."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from contractai_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentState, DocumentType


class _ScalarResult:
    def one(self):
        return 0


class _RowsResult:
    def all(self):
        return []


def _compiled_last_statement(session: AsyncMock) -> str:
    statement = session.exec.await_args.kwargs["statement"]
    return str(statement.compile(dialect=postgresql.dialect()))


def test_normalize_service_names_filters_empty_values():
    assert SQLModelDashboardRepository._normalize_service_names(["Cloud", None, ""]) == ["Cloud"]


def test_serialize_contract_row_from_mapping():
    row = {
        "id": 1,
        "title": "Contrato Marco",
        "name": "TechCorp",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "state": DocumentState.ACTIVE,
        "detail": "Cloud",
        "amount": 1200,
        "service_names": ["Cloud"],
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }

    result = SQLModelDashboardRepository._serialize_contract_row(row)

    assert result.id == 1
    assert result.name == "TechCorp"
    assert result.service_names == ["Cloud"]


@pytest.mark.asyncio
@pytest.mark.parametrize("document_type", [DocumentType.COMPANY, DocumentType.LABOR])
async def test_get_monthly_amounts_anchors_query_from_documents(document_type):
    session = AsyncMock()
    session.exec.return_value = _ScalarResult()
    repo = SQLModelDashboardRepository(session=session)

    await repo.get_monthly_amounts(
        organization_id=1,
        document_type=document_type,
        currency=None,
        start_month=date(2026, 1, 1),
        months=1,
    )

    statement = session.exec.await_args.kwargs["statement"]
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "FROM contracts.documents JOIN" in compiled


@pytest.mark.asyncio
async def test_company_monthly_amounts_uses_current_company_contract_tables():
    session = AsyncMock()
    session.exec.return_value = _ScalarResult()
    repo = SQLModelDashboardRepository(session=session)

    await repo.get_monthly_amounts(
        organization_id=1,
        document_type=DocumentType.COMPANY,
        currency=CurrencyType.PEN,
        start_month=date(2026, 1, 1),
        months=1,
    )

    compiled = _compiled_last_statement(session)

    assert "company_contracts" in compiled
    assert "company_contract_services" in compiled
    assert "documents_services" not in compiled


@pytest.mark.asyncio
async def test_labor_monthly_amounts_uses_labor_contract_table():
    session = AsyncMock()
    session.exec.return_value = _ScalarResult()
    repo = SQLModelDashboardRepository(session=session)

    await repo.get_monthly_amounts(
        organization_id=1,
        document_type=DocumentType.LABOR,
        currency=CurrencyType.PEN,
        start_month=date(2026, 1, 1),
        months=1,
    )

    compiled = _compiled_last_statement(session)

    assert "labor_contracts" in compiled
    assert "company_contract_services" not in compiled
    assert "documents_services" not in compiled


@pytest.mark.asyncio
async def test_top_companies_uses_current_company_contract_tables():
    session = AsyncMock()
    session.exec.return_value = _RowsResult()
    repo = SQLModelDashboardRepository(session=session)

    await repo.list_top_companies(
        organization_id=1,
        limit=5,
        currency=CurrencyType.USD,
        sort_by=TopRankingSortBy.VALUE,
    )

    compiled = _compiled_last_statement(session)

    assert "company_contracts" in compiled
    assert "company_contract_services" in compiled
    assert "documents_services" not in compiled


@pytest.mark.asyncio
async def test_top_services_uses_current_service_link_tables():
    session = AsyncMock()
    session.exec.return_value = _RowsResult()
    repo = SQLModelDashboardRepository(session=session)

    await repo.list_top_services(
        organization_id=1,
        limit=5,
        currency=CurrencyType.PEN,
        sort_by=TopRankingSortBy.VOLUME,
    )

    compiled = _compiled_last_statement(session)

    assert "services" in compiled
    assert "company_contracts" in compiled
    assert "company_contract_services" in compiled
    assert "documents_services" not in compiled
