"""Dashboard integration tests backed by a PostgreSQL test database."""

from datetime import date

import pytest
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from pactus_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from pactus_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from pactus_backend.modules.documents.domain.value_objs import CurrencyType, DocumentType


async def _seed_dashboard_data(session: AsyncSession) -> None:
    statements = [
        """
        insert into services (id, organization_id, name) values
          (1, 10, 'Cloud Support'),
          (2, 10, 'Legal Advisory'),
          (3, 99, 'External Service');
        """,
        """
        insert into documents (id, organization_id, type, start_date, end_date, state, created_at, updated_at) values
          (1, 10, 'manual_upload', '2026-01-01', '2026-12-31', 'ACTIVE', '2026-01-01', '2026-02-01'),
          (2, 10, 'manual_upload', '2026-01-01', '2026-01-20', 'EXPIRING_SOON', '2026-01-02', '2026-03-01'),
          (3, 10, 'manual_upload', '2026-01-01', '2026-12-31', 'DRAFT', '2026-01-03', '2026-04-01'),
          (4, 99, 'manual_upload', '2026-01-01', '2026-12-31', 'ACTIVE', '2026-01-04', '2026-05-01'),
          (5, 10, 'manual_upload', '2026-01-01', '2026-02-15', 'ACTIVE', '2026-01-05', '2026-06-01');
        """,
        """
        insert into company_contracts (id, document_id, ruc, client) values
          (1, 1, '20111111111', 'TechCorp'),
          (2, 2, '20222222222', 'Acme SAC'),
          (3, 3, '20333333333', 'Draft Client'),
          (4, 4, '20444444444', 'Other Org');
        """,
        """
        insert into labor_contracts (id, document_id, worker_name, position, salary_value, salary_currency) values
          (1, 5, 'Jane Worker', 'Developer', 2500, 'PEN');
        """,
        """
        insert into company_contract_services (id, company_contract_id, service_id, description, value, currency, start_date, end_date) values
          (1, 1, 1, 'Cloud monthly support', 1000, 'PEN', '2026-01-01', '2026-12-31'),
          (2, 1, 2, 'Legal retainer', 500, 'PEN', '2026-01-01', '2026-12-31'),
          (3, 2, 2, 'Legal advisory', 800, 'PEN', '2026-01-01', '2026-01-20'),
          (4, 2, 1, 'Cloud setup', 100, 'USD', '2026-01-01', '2026-01-20'),
          (5, 3, 1, 'Draft service', 9999, 'PEN', '2026-01-01', '2026-12-31'),
          (6, 4, 3, 'Other org service', 5000, 'PEN', '2026-01-01', '2026-12-31');
        """
    ]
    for stmt in statements:
        await session.exec(text(stmt))


@pytest.mark.asyncio
async def test_monthly_amounts_sum_active_company_services_by_currency(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)

    result = await dashboard_repo.get_monthly_amounts(
        organization_id=10,
        document_type=DocumentType.COMPANY,
        currency=CurrencyType.PEN,
        start_month=date(2026, 1, 1),
        months=2,
    )

    assert [item.month for item in result] == [date(2026, 1, 1), date(2026, 2, 1)]
    assert [item.amount for item in result] == [2300.0, 1500.0]


@pytest.mark.asyncio
async def test_monthly_amounts_sum_active_labor_salaries_by_currency(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)

    result = await dashboard_repo.get_monthly_amounts(
        organization_id=10,
        document_type=DocumentType.LABOR,
        currency=CurrencyType.PEN,
        start_month=date(2026, 1, 1),
        months=2,
    )

    assert [item.month for item in result] == [date(2026, 1, 1), date(2026, 2, 1)]
    assert [item.amount for item in result] == [2500.0, 2500.0]


@pytest.mark.asyncio
async def test_top_companies_uses_only_current_organization_active_company_contracts(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)

    result = await dashboard_repo.list_top_companies(
        organization_id=10,
        limit=5,
        currency=CurrencyType.PEN,
        sort_by=TopRankingSortBy.VALUE,
    )

    assert [(item.name, item.contracts, item.amount) for item in result] == [
        ("TechCorp", 1, 1500.0),
        ("Acme SAC", 1, 800.0),
    ]


@pytest.mark.asyncio
async def test_top_services_aggregates_company_services(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)

    result = await dashboard_repo.list_top_services(
        organization_id=10,
        limit=5,
        currency=CurrencyType.PEN,
        sort_by=TopRankingSortBy.VALUE,
    )

    assert [(item.name, item.quantity, item.amount) for item in result] == [
        ("Legal Advisory", 2, 1300.0),
        ("Cloud Support", 1, 1000.0),
    ]


@pytest.mark.asyncio
async def test_recent_contracts_returns_latest_active_contracts_for_type(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)

    result = await dashboard_repo.list_recent_contracts(organization_id=10, document_type=DocumentType.COMPANY, limit=4)

    assert [item.name for item in result] == ["Acme SAC", "TechCorp"]
    assert [item.title for item in result] == ["Acme SAC", "TechCorp"]


@pytest.mark.asyncio
async def test_origin_distribution_includes_internal_import_source_for_admin_panel(
    dashboard_repo: SQLModelDashboardRepository,
    dashboard_session: AsyncSession,
):
    await _seed_dashboard_data(dashboard_session)
    statements = [
        """
        insert into documents (id, organization_id, type, start_date, end_date, state, created_at, updated_at) values
          (6, 10, 'google_drive', '2026-01-01', '2026-08-31', 'ACTIVE', '2026-01-06', '2026-06-02');
        """,
        """
        insert into labor_contracts (id, document_id, worker_name, position, salary_value, salary_currency) values
          (2, 6, 'Drive Worker', 'Analyst', 3000, 'PEN');
        """
    ]
    for stmt in statements:
        await dashboard_session.exec(text(stmt))

    result = await dashboard_repo.get_contract_origin_distribution(organization_id=10)
    actual = [(item["origin_type"], item["count"], item["percentage"]) for item in result]
    assert sorted(actual) == sorted([
        ("Carga Manual", 1, 50.0),
        ("Importación: Google Drive", 1, 50.0),
    ])
