"""Unit-level tests for dashboard repository helpers."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from contractai_backend.modules.documents.domain.value_objs import DocumentState, DocumentType


class _ScalarResult:
    def one(self):
        return 0


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

    assert "FROM documents JOIN" in compiled
