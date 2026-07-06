"""Unit tests for dashboard alert center responses."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from pactus_backend.modules.dashboard.application.repositories import DashboardContractSummary
from pactus_backend.modules.dashboard.application.services import ALERT_PREVIEW_LIMIT, DashboardService
from pactus_backend.modules.documents.domain.value_objs import DocumentType
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole = UserRole.MANAGER) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def _make_contract(contract_id: int, *, end_date: date | None, detail: str | None = "Cloud") -> DashboardContractSummary:
    return DashboardContractSummary(
        id=contract_id,
        title=f"Contrato {contract_id}",
        name=f"Cliente {contract_id}",
        start_date=date.today(),
        end_date=end_date,
        detail=detail,
        service_names=["Cloud"],
    )


def _make_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.count_contracts_due_between.side_effect = [2, 1]
    repo.count_long_term_contracts.return_value = 3
    repo.list_contracts_due_between.side_effect = [
        [_make_contract(1, end_date=date.today() + timedelta(days=1)), _make_contract(2, end_date=date.today() + timedelta(days=15))],
        [_make_contract(3, end_date=date.today() + timedelta(days=45))],
    ]
    repo.list_long_term_contracts.return_value = [_make_contract(4, end_date=date.today() + timedelta(days=90))]
    return repo


@pytest.mark.asyncio
async def test_alert_center_builds_critical_warning_and_long_term_buckets():
    repo = _make_repo()
    service = DashboardService(repository=repo)

    response = await service.get_alert_center(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert [category.due_to for category in response] == [30, 60, None]
    assert [category.count for category in response] == [2, 1, 3]
    assert response[0].label == "VENCEN PROXIMOS"
    assert response[1].label == "VENCEN PROXIMOS"
    assert response[2].label == "VIGENCIA PROLONGADA"


@pytest.mark.asyncio
async def test_alert_center_uses_expected_date_windows():
    repo = _make_repo()
    service = DashboardService(repository=repo)
    today = date.today()

    await service.get_alert_center(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert repo.count_contracts_due_between.await_args_list[0].args == (10, DocumentType.COMPANY, today, today + timedelta(days=30))
    assert repo.count_contracts_due_between.await_args_list[1].args == (
        10,
        DocumentType.COMPANY,
        today + timedelta(days=31),
        today + timedelta(days=60),
    )
    assert repo.count_long_term_contracts.await_args.args == (10, DocumentType.COMPANY, today + timedelta(days=60))


@pytest.mark.asyncio
async def test_alert_center_uses_preview_limit_three():
    repo = _make_repo()
    service = DashboardService(repository=repo)

    await service.get_alert_center(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert repo.list_contracts_due_between.await_args_list[0].args[-1] == ALERT_PREVIEW_LIMIT
    assert repo.list_contracts_due_between.await_args_list[1].args[-1] == ALERT_PREVIEW_LIMIT
    assert repo.list_long_term_contracts.await_args.args[-1] == ALERT_PREVIEW_LIMIT


@pytest.mark.asyncio
async def test_alert_center_formats_item_statuses():
    repo = _make_repo()
    service = DashboardService(repository=repo)

    response = await service.get_alert_center(current_user=_make_user(), document_type=DocumentType.COMPANY)

    assert response[0].items[0].status == "VENCE EN 1 DIA"
    assert response[0].items[1].status == "VENCE EN 15 DIAS"
    assert response[1].items[0].status == "VENCE EN 45 DIAS"
    assert response[2].items[0].status == "VIGENCIA PROLONGADA"


@pytest.mark.asyncio
async def test_labor_alert_items_omit_service_detail_when_contract_detail_is_absent():
    repo = AsyncMock()
    repo.sync_contract_states.return_value = 0
    repo.count_contracts_due_between.side_effect = [1, 0]
    repo.count_long_term_contracts.return_value = 0
    repo.list_contracts_due_between.side_effect = [[_make_contract(1, end_date=date.today() + timedelta(days=10), detail=None)], []]
    repo.list_long_term_contracts.return_value = []
    service = DashboardService(repository=repo)

    response = await service.get_alert_center(current_user=_make_user(UserRole.HR), document_type=DocumentType.LABOR)

    assert response[0].items[0].detail is None
