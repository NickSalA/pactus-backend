"""Unit-level tests for dashboard repository helpers."""

from datetime import UTC, date, datetime

from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository
from contractai_backend.modules.documents.domain.value_objs import DocumentState


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
