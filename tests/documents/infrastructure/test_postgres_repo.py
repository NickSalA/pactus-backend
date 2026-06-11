"""Tests unitarios para repositories SQLModel de documents con sesión mockeada."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from contractai_backend.core.exceptions.base import ServiceUnavailableError
from contractai_backend.modules.catalog.domain.entities import ServiceTable
from contractai_backend.modules.documents.application.dto import CompanyContractQueryDTO
from contractai_backend.modules.documents.domain import CompanyContractTable, DocumentServiceTable, DocumentTable
from contractai_backend.modules.documents.domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentState
from contractai_backend.modules.documents.infrastructure.command_repo import SQLModelDocumentCommandRepository
from contractai_backend.modules.documents.infrastructure.query_repo import SQLModelDocumentQueryRepository


def _make_doc(id: int = 1) -> DocumentTable:
    return DocumentTable(
        id=id,
        organization_id=1,
        type="manual_upload",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        form_data={"value": 120.0, "currency": "PEN"},
        state=DocumentState.ACTIVE,
    )


def _make_document_service(id: int = 1) -> DocumentServiceTable:
    return DocumentServiceTable(
        id=id,
        company_contract_id=id,
        service_id=2,
        description="Hosting",
        value=120.0,
        currency=CurrencyType.PEN,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 6, 1),
    )


def _make_service(id: int = 2) -> ServiceTable:
    return ServiceTable(id=id, organization_id=1, name="Hosting")


def _make_repo() -> tuple[SQLModelDocumentQueryRepository, AsyncMock]:
    session = AsyncMock()
    session.add_all = MagicMock()
    repo = SQLModelDocumentQueryRepository(session=session)
    return repo, session


def _make_command_repo() -> tuple[SQLModelDocumentCommandRepository, AsyncMock]:
    session = AsyncMock()
    session.add_all = MagicMock()
    repo = SQLModelDocumentCommandRepository(session=session)
    return repo, session


class TestSearchContracts:
    @pytest.mark.asyncio
    async def test_returns_documents_for_query(self):
        repo, session = _make_repo()
        docs = [_make_doc(1), _make_doc(2)]

        result_mock = MagicMock()
        result_mock.all.return_value = docs
        session.exec.return_value = result_mock

        result = await repo.search_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="list", client="Cliente Test"))

        assert result == docs
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_applies_service_name_filter_without_duplicate_join_rows(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        await repo.search_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="list", service_name="Hosting"))

        statement = session.exec.await_args.kwargs["statement"]
        compiled = statement.compile()
        assert "company_contract_services" in str(statement)
        assert "services" in str(statement)
        assert any(value == "%hosting%" for value in compiled.params.values())

    @pytest.mark.asyncio
    async def test_operational_error_raises_unavailable(self):
        repo, session = _make_repo()
        session.exec.side_effect = OperationalError("conn", {}, Exception())

        with pytest.raises(DocumentDatabaseUnavailableError):
            await repo.search_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="list", client="Cliente Test"))

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_raises_database_error(self):
        repo, session = _make_repo()
        session.exec.side_effect = SQLAlchemyError("query error")

        with pytest.raises(DocumentDatabaseError):
            await repo.search_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="list", client="Cliente Test"))


class TestCountContracts:
    @pytest.mark.asyncio
    async def test_returns_contract_count(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.one.return_value = 1
        session.exec.return_value = result_mock

        result = await repo.count_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="count"))

        assert result == 1

    @pytest.mark.asyncio
    async def test_applies_service_id_filter(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.one.return_value = 1
        session.exec.return_value = result_mock

        await repo.count_company_contracts(organization_id=1, query=CompanyContractQueryDTO(operation="count", service_id=2))

        statement = session.exec.await_args.kwargs["statement"]
        compiled = statement.compile()
        assert "company_contract_services" in str(statement)
        assert any(value == 2 for value in compiled.params.values())


class TestRankContractsByClient:
    @pytest.mark.asyncio
    async def test_returns_client_ranking_rows(self):
        repo, session = _make_repo()
        first_row = MagicMock()
        first_row._mapping = {
            "client": "Cliente A",
            "currency": "USD",
            "total_value": 1500.0,
            "contracts_count": 3,
        }
        second_row = MagicMock()
        second_row._mapping = {
            "client": "Cliente B",
            "currency": "PEN",
            "total_value": 300.0,
            "contracts_count": 1,
        }
        result_mock = MagicMock()
        result_mock.all.return_value = [first_row, second_row]
        session.exec.return_value = result_mock

        result = await repo.rank_company_contracts_by_client(
            organization_id=1,
            query=CompanyContractQueryDTO(operation="ranking", currently_active=True, sort_by="total_value", sort_direction="desc"),
            limit=10,
        )

        assert result == [
            {"client": "Cliente A", "currency": "USD", "total_value": 1500.0, "contracts_count": 3},
            {"client": "Cliente B", "currency": "PEN", "total_value": 300.0, "contracts_count": 1},
        ]
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_applies_service_filters_to_ranking_query(self):
        repo, session = _make_repo()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        await repo.rank_company_contracts_by_client(
            organization_id=1,
            query=CompanyContractQueryDTO(operation="ranking", service_name="Hosting", service_id=2),
            limit=10,
        )

        statement = session.exec.await_args.kwargs["statement"]
        compiled = statement.compile()
        assert "company_contract_services" in str(statement)
        assert "services" in str(statement)
        assert any(value == 2 for value in compiled.params.values())
        assert any(value == "%hosting%" for value in compiled.params.values())

    @pytest.mark.asyncio
    async def test_operational_error_raises_unavailable(self):
        repo, session = _make_repo()
        session.exec.side_effect = OperationalError("conn", {}, Exception())

        with pytest.raises(DocumentDatabaseUnavailableError):
            await repo.rank_company_contracts_by_client(organization_id=1, query=CompanyContractQueryDTO(operation="ranking"))


class TestGetDocumentServices:
    @pytest.mark.asyncio
    async def test_returns_document_services(self):
        repo, session = _make_repo()
        service_items = [_make_document_service()]
        result_mock = MagicMock()
        result_mock.all.return_value = service_items
        session.exec.return_value = result_mock

        result = await repo.get_document_services(doc_id=1)

        assert result == service_items
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_raises_document_database_unavailable(self):
        repo, session = _make_repo()
        session.exec.side_effect = SQLAlchemyTimeoutError("pool exhausted")

        with pytest.raises(DocumentDatabaseUnavailableError):
            await repo.get_document_services(doc_id=1)


class TestInheritedGetAll:
    @pytest.mark.asyncio
    async def test_timeout_raises_service_unavailable(self):
        repo, session = _make_repo()
        session.exec.side_effect = SQLAlchemyTimeoutError("pool exhausted")

        with pytest.raises(ServiceUnavailableError):
            await repo.get_all(filters={"organization_id": 1})


class TestGetDocumentServicesByDocumentIds:
    @pytest.mark.asyncio
    async def test_groups_services_by_document_id(self):
        repo, session = _make_repo()
        first_item = _make_document_service(1)
        second_item = _make_document_service(2)
        result_mock = MagicMock()
        result_mock.all.return_value = [(first_item, 1), (second_item, 2)]
        session.exec.return_value = result_mock

        result = await repo.get_document_services_by_document_ids(document_ids=[1, 2])

        assert result == {1: [first_item], 2: [second_item]}
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_document_ids_returns_empty_mapping(self):
        repo, session = _make_repo()

        result = await repo.get_document_services_by_document_ids(document_ids=[])

        assert result == {}
        session.exec.assert_not_called()


class TestReplaceDocumentServices:
    @pytest.mark.asyncio
    async def test_replaces_services_and_commits(self):
        repo, session = _make_command_repo()
        service_items = [_make_document_service()]
        company_contract_result = MagicMock()
        company_contract_result.first.return_value = CompanyContractTable(id=1, document_id=1, client="Cliente Test")
        delete_result = MagicMock()
        select_result = MagicMock()
        select_result.all.return_value = service_items
        session.exec.side_effect = [company_contract_result, delete_result, select_result]

        result = await repo.replace_document_services(doc_id=1, service_items=service_items)

        assert result == service_items
        assert session.exec.call_count == 3
        session.add_all.assert_called_once_with(service_items)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlalchemy_error_rolls_back(self):
        repo, session = _make_command_repo()
        session.exec.side_effect = SQLAlchemyError("boom")

        with pytest.raises(DocumentDatabaseError):
            await repo.replace_document_services(doc_id=1, service_items=[])

        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_replaces_multiple_services_and_returns_reloaded_rows(self):
        repo, session = _make_command_repo()
        service_items = [_make_document_service(1), _make_document_service(2)]
        company_contract_result = MagicMock()
        company_contract_result.first.return_value = CompanyContractTable(id=1, document_id=1, client="Cliente Test")
        delete_result = MagicMock()
        select_result = MagicMock()
        select_result.all.return_value = service_items
        session.exec.side_effect = [company_contract_result, delete_result, select_result]

        result = await repo.replace_document_services(doc_id=1, service_items=service_items)

        assert result == service_items
        session.add_all.assert_called_once_with(service_items)
        session.commit.assert_called_once()


class TestGetServicesByIds:
    @pytest.mark.asyncio
    async def test_returns_services_for_ids(self):
        repo, session = _make_repo()
        services = [_make_service()]
        result_mock = MagicMock()
        result_mock.all.return_value = services
        session.exec.return_value = result_mock

        result = await repo.get_services_by_ids(organization_id=1, service_ids=[2])

        assert result == services
        session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_list_without_query(self):
        repo, session = _make_repo()

        result = await repo.get_services_by_ids(organization_id=1, service_ids=[])

        assert result == []
        session.exec.assert_not_called()


class TestGetServices:
    @pytest.mark.asyncio
    async def test_returns_service_catalog_for_organization(self):
        repo, session = _make_repo()
        services = [_make_service()]
        result_mock = MagicMock()
        result_mock.all.return_value = services
        session.exec.return_value = result_mock

        result = await repo.get_services(organization_id=1)

        assert result == services
        session.exec.assert_called_once()
