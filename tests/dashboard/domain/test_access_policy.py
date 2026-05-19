"""Unit tests for dashboard access policy."""

import pytest

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.dashboard.domain.access_policy import ensure_dashboard_access
from contractai_backend.modules.documents.domain.value_objs import DocumentType
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_user(role: UserRole) -> UserTable:
    return UserTable(id=1, organization_id=10, email="user@example.com", role=role, is_active=True)


def test_manager_can_access_company_dashboard():
    ensure_dashboard_access(current_user=_make_user(UserRole.MANAGER), document_type=DocumentType.COMPANY)


def test_hr_can_access_labor_dashboard():
    ensure_dashboard_access(current_user=_make_user(UserRole.HR), document_type=DocumentType.LABOR)


def test_manager_cannot_access_labor_dashboard():
    with pytest.raises(ForbiddenError):
        ensure_dashboard_access(current_user=_make_user(UserRole.MANAGER), document_type=DocumentType.LABOR)


def test_hr_cannot_access_company_dashboard():
    with pytest.raises(ForbiddenError):
        ensure_dashboard_access(current_user=_make_user(UserRole.HR), document_type=DocumentType.COMPANY)


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.WORKER])
@pytest.mark.parametrize("document_type", [DocumentType.COMPANY, DocumentType.LABOR])
def test_admin_and_worker_cannot_access_dashboard(role: UserRole, document_type: DocumentType):
    with pytest.raises(ForbiddenError):
        ensure_dashboard_access(current_user=_make_user(role), document_type=document_type)
