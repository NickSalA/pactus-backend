"""B2B client loyalty analytics queries for dashboard."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from ....documents.domain import CompanyContractTable, DocumentTable
from ...domain.exceptions import DashboardDatabaseError, DashboardDatabaseUnavailableError
from .helpers import ACTIVE_DASHBOARD_STATES, DashboardRepositoryProtocol


class DashboardCompanyLoyaltyQueriesMixin:
    """Query mixin for B2B client loyalty and recurrence analytics."""

    async def get_company_loyalty_kpi_data(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> dict[str, Any]:
        """Computes key client loyalty KPIs: unique clients, contract count and recurrence rate."""
        try:
            client_id_expr = func.coalesce(
                col(CompanyContractTable.ruc),
                col(CompanyContractTable.client),
            )
            # Find all unique B2B clients with their total contract counts and active states
            statement = (
                sa_select(
                    client_id_expr.label("client_id"),
                    func.count(col(DocumentTable.id)).label("total_contracts"),
                    func.max(
                        case(
                            (col(DocumentTable.state).in_(ACTIVE_DASHBOARD_STATES), 1),
                            else_=0,
                        )
                    ).label("is_active"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(client_id_expr)
            )

            result = await self.session.exec(statement)
            rows = result.all()

            total_unique_clients = len(rows)
            if total_unique_clients == 0:
                return {
                    "active_retention_rate": 0.0,
                    "total_unique_clients": 0,
                    "avg_contracts_per_client": 0.0,
                }

            total_contracts_sum = sum(int(r.total_contracts or 0) for r in rows)
            avg_contracts = float(total_contracts_sum) / total_unique_clients

            active_clients_count = sum(bool(r.is_active) for r in rows)
            recurrent_active_clients_count = sum(bool(r.is_active and (r.total_contracts or 0) >= 2) for r in rows)

            active_retention_rate = (float(recurrent_active_clients_count) / active_clients_count) * 100.0 if active_clients_count > 0 else 0.0

            return {
                "active_retention_rate": round(active_retention_rate, 2),
                "total_unique_clients": total_unique_clients,
                "avg_contracts_per_client": round(avg_contracts, 2),
            }

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar los KPIs de fidelidad de clientes.") from e

    async def get_company_tenure_distribution(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> list[dict[str, int]]:
        """Returns the distribution of B2B clients grouped by signed contracts count."""
        try:
            client_id_expr = func.coalesce(
                col(CompanyContractTable.ruc),
                col(CompanyContractTable.client),
            )
            subquery = (
                select(
                    client_id_expr.label("client_id"),
                    func.count(col(DocumentTable.id)).label("contracts_count"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(client_id_expr)
                .subquery()
            )

            statement = (
                sa_select(
                    subquery.c.contracts_count,
                    func.count().label("clients_count"),
                )
                .group_by(subquery.c.contracts_count)
                .order_by(subquery.c.contracts_count)
            )

            result = await self.session.exec(statement)
            rows = result.all()

            # Group everything into buckets (1, 2, 3, 4+)
            buckets = {1: 0, 2: 0, 3: 0, 4: 0}
            for row in rows:
                c_count = int(row.contracts_count or 0)
                cl_count = int(row.clients_count or 0)
                if c_count == 1:
                    buckets[1] += cl_count
                elif c_count == 2:
                    buckets[2] += cl_count
                elif c_count == 3:
                    buckets[3] += cl_count
                else:
                    buckets[4] += cl_count

            return [
                {"contracts_count": 1, "clients_count": buckets[1]},
                {"contracts_count": 2, "clients_count": buckets[2]},
                {"contracts_count": 3, "clients_count": buckets[3]},
                {"contracts_count": 4, "clients_count": buckets[4]},  # represents 4+
            ]

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar la distribución de permanencia de clientes.") from e

    async def get_company_monthly_renewal_trend(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        months: int = 6,
    ) -> list[dict[str, Any]]:
        """Returns monthly B2B client cohort renewal rates for clients whose contracts expired in each of the past 6 months."""
        try:
            # Query all company contracts for the organization to analyze historical sequences
            statement = (
                sa_select(
                    func.coalesce(
                        col(CompanyContractTable.ruc),
                        col(CompanyContractTable.client),
                    ).label("client_id"),
                    col(DocumentTable.id).label("contract_id"),
                    col(DocumentTable.start_date).label("start_date"),
                    col(DocumentTable.end_date).label("end_date"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .where(col(DocumentTable.start_date).is_not(None))
                .where(col(DocumentTable.end_date).is_not(None))
                .order_by(col(DocumentTable.start_date))
            )

            result = await self.session.exec(statement)
            contracts = result.all()

            # Group contracts by client
            client_contracts: dict[str, list[Any]] = defaultdict(list)
            for c in contracts:
                client_contracts[c.client_id].append(c)

            # Generate past 6 months endpoints
            today = date.today()
            month_cohorts: list[tuple[date, date, str]] = []

            # Helper to get month name in Spanish
            month_names = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

            current_year = today.year
            current_month = today.month
            for _ in range(months):
                cohort_start = date(current_year, current_month, 1)
                cohort_end = self._month_end(cohort_start)
                label = f"{month_names[current_month]} {str(current_year)[2:]}"
                month_cohorts.insert(0, (cohort_start, cohort_end, label))

                # Step backward
                current_month -= 1
                if current_month == 0:
                    current_month = 12
                    current_year -= 1

            cohort_results = []
            for cohort_start, cohort_end, label in month_cohorts:
                total_expired = 0
                total_renewed = 0

                for c_list in client_contracts.values():
                    for c in c_list:
                        # Did this contract end in the cohort month?
                        if cohort_start <= c.end_date < cohort_end:
                            total_expired += 1
                            # Did this client have any subsequent contract starting after this one ended?
                            # (within a standard grace period of 60 days to count as a retention/renewal)
                            limit_date = c.end_date + timedelta(days=60)
                            has_subsequent = any(
                                other.contract_id != c.contract_id and c.end_date <= other.start_date <= limit_date for other in c_list
                            )
                            if has_subsequent:
                                total_renewed += 1

                rate = (float(total_renewed) / total_expired * 100.0) if total_expired > 0 else 0.0
                cohort_results.append(
                    {
                        "month": label,
                        "renewal_rate": round(rate, 2),
                        "total_expired": total_expired,
                        "total_renewed": total_renewed,
                    }
                )

            return cohort_results

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar la tendencia de renovación mensual de clientes.") from e

    async def get_company_loyalty_details(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> list[dict[str, Any]]:
        """Returns details for each unique client, including contract count and employment date ranges."""
        try:
            client_id_expr = func.coalesce(
                col(CompanyContractTable.ruc),
                col(CompanyContractTable.client),
            )
            statement = (
                sa_select(
                    func.max(col(CompanyContractTable.client)).label("client_name"),
                    col(CompanyContractTable.ruc).label("ruc"),
                    func.count(col(DocumentTable.id)).label("contracts_count"),
                    func.min(col(DocumentTable.start_date)).label("first_contract_start"),
                    func.max(col(DocumentTable.end_date)).label("latest_contract_end"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(col(CompanyContractTable.ruc), client_id_expr)
                .order_by(func.count(col(DocumentTable.id)).desc(), func.max(col(CompanyContractTable.client)))
            )

            result = await self.session.exec(statement)
            rows = result.all()

            return [
                {
                    "client_name": r.client_name or "Sin nombre",
                    "ruc": r.ruc,
                    "contracts_count": int(r.contracts_count or 0),
                    "first_contract_start": r.first_contract_start.isoformat() if r.first_contract_start else None,
                    "latest_contract_end": r.latest_contract_end.isoformat() if r.latest_contract_end else None,
                }
                for r in rows
            ]

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar los detalles de fidelidad de clientes.") from e
