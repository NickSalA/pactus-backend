"""Alert center queries for dashboard analytics."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import desc, func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from .....core.exceptions.base import InternalServerError, ServiceUnavailableError
from ....documents.domain import CompanyContractTable, DocumentTable, LaborContractTable
from ....documents.domain.value_objs import DocumentType
from ...application.repositories import DashboardContractSummary
from .helpers import DashboardRepositoryProtocol


class DashboardAlertQueriesMixin:
    """Query mixin for counting and listing due and long-term contracts."""

    async def count_contracts_due_between(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
    ) -> int:
        """Counts contracts due in a date range."""
        try:
            statement = select(func.count(col(DocumentTable.id)))
            if document_type == DocumentType.COMPANY:
                statement = statement.join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
            else:
                statement = statement.join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
            statement = statement.where(
                *self._base_contract_filters(organization_id=organization_id),
                col(DocumentTable.end_date) >= start_date,
                col(DocumentTable.end_date) <= end_date,
            )
            result = await self.session.exec(statement=statement)
            return int(result.one() or 0)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al contar contratos en alerta") from e

    async def list_contracts_due_between(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists contracts due in a date range."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(
                    *self._base_contract_filters(organization_id=organization_id),
                    col(DocumentTable.end_date) >= start_date,
                    col(DocumentTable.end_date) <= end_date,
                )
                .order_by(col(DocumentTable.end_date), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos en alerta") from e

    async def count_long_term_contracts(
        self: DashboardRepositoryProtocol, organization_id: int, document_type: DocumentType, after_date: date
    ) -> int:
        """Counts active contracts outside the alert window."""
        try:
            statement = select(func.count(col(DocumentTable.id)))
            if document_type == DocumentType.COMPANY:
                statement = statement.join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
            else:
                statement = statement.join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
            statement = statement.where(
                *self._base_contract_filters(organization_id=organization_id),
                col(DocumentTable.end_date) > after_date,
            )
            result = await self.session.exec(statement=statement)
            return int(result.one() or 0)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al contar contratos de vigencia prolongada") from e

    async def list_long_term_contracts(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        document_type: DocumentType,
        after_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists active contracts outside the alert window."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(
                    *self._base_contract_filters(organization_id=organization_id),
                    col(DocumentTable.end_date) > after_date,
                )
                .order_by(desc(col(DocumentTable.end_date)), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos de vigencia prolongada") from e
