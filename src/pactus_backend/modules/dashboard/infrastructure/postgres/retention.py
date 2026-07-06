"""Worker retention analytics queries for dashboard."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from ....documents.domain import DocumentTable, LaborContractTable
from ...domain.exceptions import DashboardDatabaseError, DashboardDatabaseUnavailableError
from .helpers import ACTIVE_DASHBOARD_STATES, DashboardRepositoryProtocol


def _group_contracts_by_worker(contracts: list[Any]) -> dict[str, list[Any]]:
    worker_contracts: dict[str, list[Any]] = defaultdict(list)
    for c in contracts:
        worker_contracts[c.worker_id].append(c)
    return worker_contracts


def _generate_month_cohorts(months: int, month_end_fn: Any) -> list[tuple[date, date, str]]:
    today = date.today()
    month_cohorts: list[tuple[date, date, str]] = []
    month_names = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

    current_year = today.year
    current_month = today.month
    for _ in range(months):
        cohort_start = date(current_year, current_month, 1)
        cohort_end = month_end_fn(cohort_start)
        label = f"{month_names[current_month]} {str(current_year)[2:]}"
        month_cohorts.insert(0, (cohort_start, cohort_end, label))

        current_month -= 1
        if current_month == 0:
            current_month = 12
            current_year -= 1
    return month_cohorts


def _is_contract_renewed(c: Any, c_list: list[Any]) -> bool:
    limit_date = c.end_date + timedelta(days=60)
    return any(other.contract_id != c.contract_id and c.end_date <= other.start_date <= limit_date for other in c_list)


def _calculate_cohort_metrics(worker_contracts: dict[str, list[Any]], cohort_start: date, cohort_end: date) -> tuple[int, int]:
    total_expired = 0
    total_renewed = 0
    for c_list in worker_contracts.values():
        for c in c_list:
            if cohort_start <= c.end_date < cohort_end:
                total_expired += 1
                if _is_contract_renewed(c, c_list):
                    total_renewed += 1
    return total_expired, total_renewed


def _calculate_cohort_results(worker_contracts: dict[str, list[Any]], month_cohorts: list[tuple[date, date, str]]) -> list[dict[str, Any]]:
    cohort_results = []
    for cohort_start, cohort_end, label in month_cohorts:
        total_expired, total_renewed = _calculate_cohort_metrics(worker_contracts, cohort_start, cohort_end)
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


class DashboardRetentionQueriesMixin:
    """Query mixin for worker retention analytics."""

    async def get_retention_kpi_data(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> dict[str, Any]:
        """Computes key retention KPIs: unique workers, contract count and retention rate."""
        try:
            worker_id_expr = func.coalesce(
                col(LaborContractTable.worker_document_number),
                col(LaborContractTable.worker_name),
            )
            # Find all unique workers with their total contract counts and active states
            statement = (
                select(
                    worker_id_expr.label("worker_id"),
                    func.count(col(DocumentTable.id)).label("total_contracts"),
                    func.max(
                        case(
                            (col(DocumentTable.state).in_(ACTIVE_DASHBOARD_STATES), 1),
                            else_=0,
                        )
                    ).label("is_active"),
                )
                .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(worker_id_expr)
            )

            result = await self.session.exec(statement)
            rows = result.all()

            total_unique_workers = len(rows)
            if total_unique_workers == 0:
                return {
                    "active_retention_rate": 0.0,
                    "total_unique_workers": 0,
                    "avg_contracts_per_worker": 0.0,
                }

            total_contracts_sum = sum(int(r.total_contracts or 0) for r in rows)
            avg_contracts = float(total_contracts_sum) / total_unique_workers

            active_workers_count = sum(bool(r.is_active) for r in rows)
            recurrent_active_workers_count = sum(bool(r.is_active and (r.total_contracts or 0) >= 2) for r in rows)

            active_retention_rate = (float(recurrent_active_workers_count) / active_workers_count) * 100.0 if active_workers_count > 0 else 0.0

            return {
                "active_retention_rate": round(active_retention_rate, 2),
                "total_unique_workers": total_unique_workers,
                "avg_contracts_per_worker": round(avg_contracts, 2),
            }

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar los KPIs de retención.") from e

    async def get_tenure_distribution(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> list[dict[str, int]]:
        """Returns the distribution of workers grouped by total contracts count."""
        try:
            worker_id_expr = func.coalesce(
                col(LaborContractTable.worker_document_number),
                col(LaborContractTable.worker_name),
            )
            subquery = (
                select(
                    worker_id_expr.label("worker_id"),
                    func.count(col(DocumentTable.id)).label("contracts_count"),
                )
                .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(worker_id_expr)
                .subquery()
            )

            statement = (
                select(
                    subquery.c.contracts_count,
                    func.count().label("workers_count"),
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
                w_count = int(row.workers_count or 0)
                if c_count == 1:
                    buckets[1] += w_count
                elif c_count == 2:
                    buckets[2] += w_count
                elif c_count == 3:
                    buckets[3] += w_count
                else:
                    buckets[4] += w_count

            return [
                {"contracts_count": 1, "workers_count": buckets[1]},
                {"contracts_count": 2, "workers_count": buckets[2]},
                {"contracts_count": 3, "workers_count": buckets[3]},
                {"contracts_count": 4, "workers_count": buckets[4]},  # represents 4+
            ]

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar la distribución de permanencia.") from e

    async def get_monthly_renewal_trend(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        months: int = 6,
    ) -> list[dict[str, Any]]:
        """Returns monthly cohort renewal rates for workers whose contracts expired in each of the past 6 months."""
        try:
            statement = (
                select(
                    func.coalesce(
                        col(LaborContractTable.worker_document_number),
                        col(LaborContractTable.worker_name),
                    ).label("worker_id"),
                    col(DocumentTable.id).label("contract_id"),
                    col(DocumentTable.start_date).label("start_date"),
                    col(DocumentTable.end_date).label("end_date"),
                )
                .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .where(col(DocumentTable.start_date).is_not(None))
                .where(col(DocumentTable.end_date).is_not(None))
                .order_by(col(DocumentTable.start_date))
            )
            result = await self.session.exec(statement)
            contracts = list(result.all())

            worker_contracts = _group_contracts_by_worker(contracts)
            month_cohorts = _generate_month_cohorts(months, self._month_end)
            return _calculate_cohort_results(worker_contracts, month_cohorts)

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar la tendencia de renovación mensual.") from e

    async def get_worker_retention_details(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> list[dict[str, Any]]:
        """Returns details for each unique worker, including contract count and employment date ranges."""
        try:
            worker_id_expr = func.coalesce(
                col(LaborContractTable.worker_document_number),
                col(LaborContractTable.worker_name),
            )
            statement = (
                sa_select(
                    func.max(col(LaborContractTable.worker_name)).label("worker_name"),
                    col(LaborContractTable.worker_document_number).label("worker_document_number"),
                    func.count(col(DocumentTable.id)).label("contracts_count"),
                    func.min(col(DocumentTable.start_date)).label("first_contract_start"),
                    func.max(col(DocumentTable.end_date)).label("latest_contract_end"),
                )
                .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(col(LaborContractTable.worker_document_number), worker_id_expr)
                .order_by(func.count(col(DocumentTable.id)).desc(), func.max(col(LaborContractTable.worker_name)))
            )

            result = await self.session.exec(statement)
            rows = result.all()

            return [
                {
                    "worker_name": r.worker_name or "Sin nombre",
                    "worker_document_number": r.worker_document_number,
                    "contracts_count": int(r.contracts_count or 0),
                    "first_contract_start": r.first_contract_start.isoformat() if r.first_contract_start else None,
                    "latest_contract_end": r.latest_contract_end.isoformat() if r.latest_contract_end else None,
                }
                for r in rows
            ]

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar los detalles de retención.") from e
