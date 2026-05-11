"""Unit-level tests for dashboard repository helpers and query construction."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from contractai_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentState, DocumentType


def _make_repo() -> tuple[SQLModelDashboardRepository, AsyncMock]:
    session = AsyncMock()
    repo = SQLModelDashboardRepository(session=session)
    return repo, session


def _compiled_values(statement) -> list[object]:
    values: list[object] = []
    for value in statement.compile().params.values():
        if isinstance(value, (list, tuple, set, frozenset)):
            values.extend(value)
        else:
            values.append(value)
    return values


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
async def test_sync_contract_states_calls_database_function_with_organization_id():
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.one.return_value = 4
    session.exec.return_value = result_mock

    result = await repo.sync_contract_states(organization_id=10)

    assert result == 4
    assert "sync_document_states" in str(session.exec.await_args.args[0])
    assert session.exec.await_args.kwargs["params"] == {"organization_id": 10}


@pytest.mark.asyncio
async def test_count_contracts_due_between_applies_dashboard_scope_filters():
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.one.return_value = 2
    session.exec.return_value = result_mock

    result = await repo.count_contracts_due_between(
        organization_id=10,
        document_type=DocumentType.COMPANY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    statement = session.exec.await_args.kwargs["statement"]
    compiled_values = _compiled_values(statement)
    assert result == 2
    assert DocumentType.COMPANY in compiled_values
    assert DocumentState.ACTIVE in compiled_values
    assert DocumentState.EXPIRING_SOON in compiled_values
    assert date(2026, 1, 1) in compiled_values
    assert date(2026, 1, 31) in compiled_values
    assert "documents.name IS NOT NULL" in str(statement)
    assert "documents.client IS NOT NULL" in str(statement)


@pytest.mark.asyncio
async def test_get_monthly_amounts_applies_currency_and_service_window_filters():
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.one.return_value = 1500.0
    session.exec.return_value = result_mock

    result = await repo.get_monthly_amounts(
        organization_id=10,
        document_type=DocumentType.COMPANY,
        currency=CurrencyType.PEN,
        start_month=date(2026, 1, 1),
        months=1,
    )

    statement = session.exec.await_args.kwargs["statement"]
    compiled_values = _compiled_values(statement)
    assert result[0].month == date(2026, 1, 1)
    assert result[0].amount == 1500.0
    assert CurrencyType.PEN in compiled_values
    assert DocumentType.COMPANY in compiled_values
    assert DocumentState.ACTIVE in compiled_values
    assert "documents_services" in str(statement)
    assert "documents_services.value" in str(statement)
    assert "documents_services.start_date" in str(statement)
    assert "documents_services.end_date" in str(statement)


@pytest.mark.asyncio
async def test_list_top_companies_applies_currency_sort_and_limit():
    repo, session = _make_repo()
    row = MagicMock()
    row._mapping = {"name": "TechCorp", "contracts": 3, "amount": 9000.0}
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    session.exec.return_value = result_mock

    result = await repo.list_top_companies(
        organization_id=10,
        limit=5,
        currency=CurrencyType.USD,
        sort_by=TopRankingSortBy.VALUE,
    )

    statement = session.exec.await_args.kwargs["statement"]
    compiled_values = _compiled_values(statement)
    assert result[0].name == "TechCorp"
    assert result[0].contracts == 3
    assert result[0].amount == 9000.0
    assert CurrencyType.USD in compiled_values
    assert DocumentType.COMPANY in compiled_values
    assert "documents_services" in str(statement)
    assert "ORDER BY amount DESC" in str(statement)
    assert statement._limit_clause.value == 5


@pytest.mark.asyncio
async def test_list_top_services_applies_currency_sort_and_limit():
    repo, session = _make_repo()
    row = MagicMock()
    row._mapping = {"name": "Cloud Support", "quantity": 4, "amount": 12000.0}
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    session.exec.return_value = result_mock

    result = await repo.list_top_services(
        organization_id=10,
        limit=5,
        currency=CurrencyType.EUR,
        sort_by=TopRankingSortBy.VALUE,
    )

    statement = session.exec.await_args.kwargs["statement"]
    compiled_values = _compiled_values(statement)
    assert result[0].name == "Cloud Support"
    assert result[0].quantity == 4
    assert result[0].amount == 12000.0
    assert CurrencyType.EUR in compiled_values
    assert DocumentType.COMPANY in compiled_values
    assert "services" in str(statement)
    assert "documents_services" in str(statement)
    assert "ORDER BY amount DESC" in str(statement)
    assert statement._limit_clause.value == 5


@pytest.mark.asyncio
async def test_list_recent_contracts_applies_document_type_and_limit():
    repo, session = _make_repo()
    result_mock = MagicMock()
    result_mock.all.return_value = []
    session.exec.return_value = result_mock

    result = await repo.list_recent_contracts(organization_id=10, document_type=DocumentType.LABOR, limit=4)

    statement = session.exec.await_args.kwargs["statement"]
    compiled_values = _compiled_values(statement)
    assert result == []
    assert DocumentType.LABOR in compiled_values
    assert DocumentState.ACTIVE in compiled_values
    assert DocumentState.EXPIRING_SOON in compiled_values
    assert "ORDER BY documents.updated_at DESC" in str(statement)
    assert statement._limit_clause.value == 4
