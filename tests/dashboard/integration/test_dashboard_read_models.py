"""Dashboard integration tests backed by a real PostgreSQL test database."""

from datetime import date

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentType


async def _seed_dashboard_data(session: AsyncSession) -> None:
    await session.exec(
        text(
            """
            insert into services (id, organization_id, name) values
              (1, 10, 'Cloud Support'),
              (2, 10, 'Legal Advisory'),
              (3, 99, 'External Service');

            insert into documents (id, organization_id, name, client, type, start_date, end_date, state, created_at, updated_at) values
              (1, 10, 'Contrato Cloud A', 'TechCorp', 'COMPANY', '2026-01-01', '2026-12-31', 'ACTIVE', '2026-01-01', '2026-02-01'),
              (2, 10, 'Contrato Legal B', 'Acme SAC', 'COMPANY', '2026-01-01', '2026-01-20', 'EXPIRING_SOON', '2026-01-02', '2026-03-01'),
              (3, 10, 'Contrato Borrador', 'Draft Client', 'COMPANY', '2026-01-01', '2026-12-31', 'DRAFT', '2026-01-03', '2026-04-01'),
              (4, 99, 'Contrato Otra Org', 'Other Org', 'COMPANY', '2026-01-01', '2026-12-31', 'ACTIVE', '2026-01-04', '2026-05-01'),
              (5, 10, 'Contrato Laboral', 'Jane Worker', 'LABOR', '2026-01-01', '2026-02-15', 'ACTIVE', '2026-01-05', '2026-06-01');

            insert into documents_services (document_id, service_id, description, value, currency, start_date, end_date) values
              (1, 1, 'Cloud monthly support', 1000, 'PEN', '2026-01-01', '2026-12-31'),
              (1, 2, 'Legal retainer', 500, 'PEN', '2026-01-01', '2026-12-31'),
              (2, 2, 'Legal advisory', 800, 'PEN', '2026-01-01', '2026-01-20'),
              (2, 1, 'Cloud setup', 100, 'USD', '2026-01-01', '2026-01-20'),
              (3, 1, 'Draft service', 9999, 'PEN', '2026-01-01', '2026-12-31'),
              (4, 3, 'Other org service', 5000, 'PEN', '2026-01-01', '2026-12-31'),
              (5, 1, 'Labor payroll', 2500, 'PEN', '2026-01-01', '2026-02-15');
            """
        )
    )
    await session.commit()


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
    assert [item.title for item in result] == ["Contrato Legal B", "Contrato Cloud A"]
