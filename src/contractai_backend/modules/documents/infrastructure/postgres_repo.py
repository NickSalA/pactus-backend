"""PostgreSQL implementation of document query and command repositories."""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from difflib import SequenceMatcher
from typing import Any
from typing import cast as type_cast

from loguru import logger
from sqlalchemy import Float, asc, case, cast, desc, func, or_, text
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ....shared.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ...catalog.domain.entities import ServiceTable
from ..application.dto import ContractQueryDTO
from ..application.repositories import DocumentCommandRepository, DocumentQueryRepository
from ..domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable
from ..domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError
from ..domain.value_objs import DocumentType


class SQLModelDocumentRepository(
    RelationalHelpersMixin,
    PostgresBaseRepository[DocumentTable],
    DocumentQueryRepository,
    DocumentCommandRepository,
):
    """Document repository for query and command operations via SQLModel."""

    def __init__(self, session: AsyncSession):
        super().__init__(model=DocumentTable, session=session)

    # ──────────────────────────────────────
    #  Private filter / sort helpers
    # ──────────────────────────────────────

    @staticmethod
    def _build_contract_value_expression():
        form_data = type_cast(Any, DocumentTable.form_data)
        return cast(form_data["value"].astext, Float)

    @staticmethod
    def _build_contract_currency_expression():
        form_data = type_cast(Any, DocumentTable.form_data)
        return func.upper(form_data["currency"].astext)

    @staticmethod
    def _build_party_expression():
        return func.coalesce(col(CompanyContractTable.client), col(LaborContractTable.worker_name))

    @staticmethod
    def _build_contract_title_expression():
        return func.coalesce(col(CompanyContractTable.client), col(LaborContractTable.worker_name), col(DocumentTable.file_name))

    @staticmethod
    def _build_document_kind_expression():
        return case(
            (col(CompanyContractTable.id).is_not(None), DocumentType.COMPANY.value),
            (col(LaborContractTable.id).is_not(None), DocumentType.LABOR.value),
            else_=None,
        )

    @staticmethod
    def _join_contract_detail_tables(statement):
        return statement.outerjoin(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id)).outerjoin(
            LaborContractTable,
            col(LaborContractTable.document_id) == col(DocumentTable.id),
        )

    def _apply_period_filters(self, statement, filters: ContractQueryDTO):
        if not (filters.period_start or filters.period_end):
            return statement

        default_columns = (col(DocumentTable.end_date), col(DocumentTable.start_date))

        mode_columns = {
            "start_date": (col(DocumentTable.start_date), col(DocumentTable.start_date)),
            "end_date": (col(DocumentTable.end_date), col(DocumentTable.end_date)),
            "overlap": default_columns,
        }

        period_start_column, period_end_column = mode_columns.get(filters.date_mode, default_columns)

        if filters.period_start is not None:
            statement = statement.where(period_start_column >= filters.period_start)
        if filters.period_end is not None:
            statement = statement.where(period_end_column <= filters.period_end)
        return statement

    def _apply_current_activity_filter(self, statement, filters: ContractQueryDTO):
        if filters.currently_active is None:
            return statement

        today = date.today()
        currently_active_condition = (col(DocumentTable.start_date) <= today) & (col(DocumentTable.end_date) >= today)

        if filters.currently_active:
            return statement.where(currently_active_condition)

        return statement.where(
            or_(
                col(DocumentTable.end_date) < today,
                col(DocumentTable.start_date) > today,
            )
        )

    @staticmethod
    def _apply_chatbot_ready_contract_filters(statement):
        form_data = type_cast(Any, DocumentTable.form_data)
        return (
            statement.where(SQLModelDocumentRepository._build_party_expression().is_not(None))
            .where(SQLModelDocumentRepository._build_document_kind_expression().is_not(None))
            .where(col(DocumentTable.start_date).is_not(None))
            .where(col(DocumentTable.end_date).is_not(None))
            .where(form_data["value"].astext.is_not(None))
            .where(form_data["currency"].astext.is_not(None))
        )

    @staticmethod
    def _normalize_lookup_text(value: str | None) -> str:
        if not value:
            return ""

        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        return " ".join(re.findall(r"[a-z0-9]+", normalized.lower()))

    @classmethod
    def _compute_party_match_metrics(cls, query: str, candidate: str) -> tuple[float, float, float, float]:
        normalized_query = cls._normalize_lookup_text(query)
        normalized_candidate = cls._normalize_lookup_text(candidate)
        if not normalized_query or not normalized_candidate:
            return 0.0, 0.0, 0.0, 0.0

        if normalized_query == normalized_candidate:
            return 1.0, 1.0, 1.0, 1.0

        if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
            full_score = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
            return 0.97, 1.0, full_score, 1.0

        query_tokens = normalized_query.split()
        candidate_tokens = normalized_candidate.split()
        if not query_tokens or not candidate_tokens:
            return 0.0, 0.0, 0.0, 0.0

        token_scores: list[float] = []
        close_hits = 0
        for query_token in query_tokens:
            best_score = max(SequenceMatcher(None, query_token, candidate_token).ratio() for candidate_token in candidate_tokens)
            token_scores.append(best_score)
            if best_score >= 0.84:
                close_hits += 1

        avg_token_score = sum(token_scores) / len(token_scores)
        coverage = close_hits / len(query_tokens)
        full_score = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
        combined_score = (avg_token_score * 0.55) + (coverage * 0.30) + (full_score * 0.15)
        return combined_score, coverage, avg_token_score, full_score

    @classmethod
    def _is_viable_party_match(cls, query: str, candidate: str) -> bool:
        combined_score, coverage, avg_token_score, full_score = cls._compute_party_match_metrics(query=query, candidate=candidate)
        normalized_query = cls._normalize_lookup_text(query)
        normalized_candidate = cls._normalize_lookup_text(candidate)

        if not normalized_query or not normalized_candidate:
            return False

        if normalized_query == normalized_candidate or normalized_query in normalized_candidate or normalized_candidate in normalized_query:
            return True

        query_token_count = len(normalized_query.split())
        if query_token_count == 1:
            return combined_score >= 0.86 or full_score >= 0.90

        return coverage >= 0.75 and avg_token_score >= 0.84 and combined_score >= 0.72

    @staticmethod
    def _resolve_sort_direction(direction: str):
        return desc if direction == "desc" else asc

    def _build_order_clause(self, expression, direction: str):
        ordered_expression = self._resolve_sort_direction(direction)(expression)
        if direction == "desc":
            return ordered_expression.nulls_last()
        return ordered_expression.nulls_first()

    def _apply_contract_sorting(self, statement, query: ContractQueryDTO):
        sort_mapping = {
            "client": self._build_party_expression(),
            "name": self._build_contract_title_expression(),
            "value": self._build_contract_value_expression(),
            "start_date": col(DocumentTable.start_date),
            "end_date": col(DocumentTable.end_date),
            "currency": self._build_contract_currency_expression(),
        }

        sort_expression = sort_mapping.get(query.sort_by or "")
        if sort_expression is None:
            return statement.order_by(
                asc(col(DocumentTable.start_date)).nulls_last(),
                asc(col(DocumentTable.end_date)).nulls_last(),
                col(DocumentTable.id),
            )

        return statement.order_by(self._build_order_clause(sort_expression, query.sort_direction), col(DocumentTable.id))

    def _apply_client_ranking_sorting(
        self,
        statement,
        query: ContractQueryDTO,
        *,
        client_expression,
        currency_expression,
        total_value_expression,
        contracts_count_expression,
    ):
        ranking_sort_mapping = {
            "client": client_expression,
            "currency": currency_expression,
            "total_value": total_value_expression,
            "contracts_count": contracts_count_expression,
        }

        default_sort_expression = total_value_expression
        if query.sort_by is None:
            sort_expression = default_sort_expression
            direction = "desc"
        else:
            sort_expression = ranking_sort_mapping.get(query.sort_by, default_sort_expression)
            direction = query.sort_direction

        return statement.order_by(
            self._build_order_clause(sort_expression, direction),
            desc(contracts_count_expression),
            asc(client_expression),
        )

    def _build_service_document_ids_subquery(self, organization_id: int, filters: ContractQueryDTO):
        normalized_service_name = self._normalize_text_filter(filters.service_name)
        if filters.service_id is None and normalized_service_name is None:
            return None

        statement = (
            select(col(CompanyContractTable.document_id))
            .join(CompanyContractServiceTable, col(CompanyContractServiceTable.company_contract_id) == col(CompanyContractTable.id))
            .distinct()
        )

        if filters.service_id is not None:
            statement = statement.where(col(CompanyContractServiceTable.service_id) == filters.service_id)

        if normalized_service_name is not None:
            statement = statement.join(ServiceTable, col(ServiceTable.id) == col(CompanyContractServiceTable.service_id)).where(
                col(ServiceTable.organization_id) == organization_id,
                col(ServiceTable.name).ilike(f"%{normalized_service_name}%"),
            )

        return statement

    def _apply_service_filters(self, statement, organization_id: int, filters: ContractQueryDTO):
        service_document_ids = self._build_service_document_ids_subquery(organization_id=organization_id, filters=filters)
        if service_document_ids is None:
            return statement
        return statement.where(col(DocumentTable.id).in_(service_document_ids))

    def _apply_contract_filters(
        self,
        statement,
        organization_id: int,
        filters: ContractQueryDTO,
    ):
        """Aplica los filtros de búsqueda de contratos a la consulta base."""
        statement = self._join_contract_detail_tables(statement)
        statement = statement.where(DocumentTable.organization_id == organization_id)

        text_filters = (
            (filters.client, self._build_party_expression()),
            (filters.contract_name, self._build_contract_title_expression()),
        )
        for raw_value, field in text_filters:
            normalized_value = self._normalize_text_filter(raw_value)
            if normalized_value:
                statement = statement.where(field.ilike(f"%{normalized_value}%"))

        statement = self._apply_service_filters(statement=statement, organization_id=organization_id, filters=filters)

        contract_value = self._build_contract_value_expression()
        if filters.min_value is not None:
            statement = statement.where(contract_value >= filters.min_value)
        if filters.max_value is not None:
            statement = statement.where(contract_value <= filters.max_value)

        if filters.currency:
            statement = statement.where(self._build_contract_currency_expression() == filters.currency)

        if filters.state is not None:
            statement = statement.where(col(DocumentTable.state) == filters.state)
        if filters.document_type is not None:
            statement = statement.where(self._build_document_kind_expression() == filters.document_type.value)

        statement = self._apply_period_filters(statement=statement, filters=filters)
        return self._apply_current_activity_filter(statement=statement, filters=filters)

    # ──────────────────────────────────────
    #  DocumentQueryRepository
    # ──────────────────────────────────────

    async def get_document_services(self, doc_id: int) -> Sequence[CompanyContractServiceTable]:
        """Obtiene los servicios asociados a un documento."""
        try:
            query = (
                select(CompanyContractServiceTable)
                .join(CompanyContractTable, col(CompanyContractTable.id) == col(CompanyContractServiceTable.company_contract_id))
                .where(col(CompanyContractTable.document_id) == doc_id)
                .order_by(col(CompanyContractServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contract_access_candidates(
        self,
        organization_id: int,
        query: str,
        limit: int = 10,
        chatbot_ready_only: bool = False,
        state: str | None = None,
    ) -> Sequence[dict[str, str | int | float | None]]:
        """Searches real contracts by counterparty name for access decisions."""
        normalized_query = self._normalize_lookup_text(query)
        if not normalized_query:
            return []

        try:
            statement = self._join_contract_detail_tables(
                sa_select(
                    col(DocumentTable.id).label("document_id"),
                    self._build_contract_title_expression().label("name"),
                    self._build_party_expression().label("client"),
                    self._build_document_kind_expression().label("document_type"),
                    col(DocumentTable.file_name).label("file_name"),
                )
            )
            statement = statement.where(DocumentTable.organization_id == organization_id).where(self._build_party_expression().is_not(None))
            if chatbot_ready_only:
                statement = self._apply_chatbot_ready_contract_filters(statement)
            if state is not None:
                statement = statement.where(col(DocumentTable.state) == state)

            result = await self.session.exec(statement=statement)
            candidates: list[dict[str, str | int | float | None]] = []
            for row in result.all():
                mapping = row._mapping if hasattr(row, "_mapping") else None
                document_id = mapping["document_id"] if mapping else row[0]
                name = mapping["name"] if mapping else row[1]
                client = mapping["client"] if mapping else row[2]
                document_type = mapping["document_type"] if mapping else row[3]
                file_name = mapping["file_name"] if mapping else row[4]
                if client is None or not self._is_viable_party_match(query=normalized_query, candidate=str(client)):
                    continue

                match_score, _, _, _ = self._compute_party_match_metrics(query=normalized_query, candidate=str(client))
                candidates.append(
                    {
                        "document_id": document_id,
                        "name": name,
                        "client": client,
                        "document_type": document_type.value if hasattr(document_type, "value") else document_type,
                        "file_name": file_name,
                        "match_score": round(match_score, 6),
                    }
                )

            candidates.sort(
                key=lambda item: (
                    float(item.get("match_score") or 0.0),
                    1 if self._normalize_lookup_text(str(item.get("client"))) == normalized_query else 0,
                    str(item.get("client") or ""),
                ),
                reverse=True,
            )
            return candidates[:limit]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_document_services_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, Sequence[CompanyContractServiceTable]]:
        """Obtiene los servicios asociados a múltiples documentos en una sola consulta."""
        if not document_ids:
            return {}

        try:
            query = (
                select(CompanyContractServiceTable, col(CompanyContractTable.document_id).label("document_id"))
                .join(CompanyContractTable, col(CompanyContractTable.id) == col(CompanyContractServiceTable.company_contract_id))
                .where(col(CompanyContractTable.document_id).in_(document_ids))
                .order_by(col(CompanyContractTable.document_id), col(CompanyContractServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            grouped_services: defaultdict[int, list[CompanyContractServiceTable]] = defaultdict(list)
            for row in result.all():
                service_item = row[0]
                document_id = row[1]
                grouped_services[document_id].append(service_item)
            return dict(grouped_services)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_services_by_ids(self, organization_id: int, service_ids: Sequence[int]) -> Sequence[ServiceTable]:
        """Obtiene servicios activos por identificador para compatibilidad interna."""
        if not service_ids:
            return []

        try:
            query = select(ServiceTable).where(
                col(ServiceTable.organization_id) == organization_id,
                col(ServiceTable.id).in_(service_ids),
                col(ServiceTable.is_active).is_(True),
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_company_contract_by_document_id(self, document_id: int) -> CompanyContractTable | None:
        """Obtiene los datos company de un documento."""
        try:
            result = await self.session.exec(select(CompanyContractTable).where(col(CompanyContractTable.document_id) == document_id))
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_labor_contract_by_document_id(self, document_id: int) -> LaborContractTable | None:
        """Obtiene los datos labor de un documento."""
        try:
            result = await self.session.exec(select(LaborContractTable).where(col(LaborContractTable.document_id) == document_id))
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_contract_kinds_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, str]:
        """Infers COMPANY/LABOR kind from the child contract tables."""
        if not document_ids:
            return {}

        try:
            company_result = await self.session.exec(
                select(col(CompanyContractTable.document_id)).where(col(CompanyContractTable.document_id).in_(document_ids))
            )
            labor_result = await self.session.exec(select(col(LaborContractTable.document_id)).where(col(LaborContractTable.document_id).in_(document_ids)))
            kinds: dict[int, str] = {document_id: DocumentType.COMPANY.value for document_id in company_result.all()}
            kinds.update({document_id: DocumentType.LABOR.value for document_id in labor_result.all()})
            return kinds
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_services(self, organization_id: int, *, include_inactive: bool = False) -> Sequence[ServiceTable]:
        """Lista el catálogo de servicios para compatibilidad interna del módulo."""
        try:
            query = select(ServiceTable).where(col(ServiceTable.organization_id) == organization_id)
            if not include_inactive:
                query = query.where(col(ServiceTable.is_active).is_(True))
            query = query.order_by(col(ServiceTable.name), col(ServiceTable.id))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contracts(
        self,
        organization_id: int,
        query: ContractQueryDTO,
        limit: int | None = None,
        chatbot_ready_only: bool = False,
    ) -> Sequence[DocumentTable]:
        """Obtiene contratos aplicando filtros estructurados."""
        try:
            statement = select(DocumentTable)
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
            if chatbot_ready_only:
                statement = self._apply_chatbot_ready_contract_filters(statement)
            statement = self._apply_contract_sorting(statement=statement, query=query)

            if limit is not None:
                statement = statement.limit(limit)

            result = await self.session.exec(statement=statement)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def rank_contracts_by_client(
        self,
        organization_id: int,
        query: ContractQueryDTO,
        limit: int | None = None,
        chatbot_ready_only: bool = False,
    ) -> Sequence[dict[str, object]]:
        """Construye un ranking agregado por cliente y moneda."""
        try:
            client_field = self._build_party_expression()
            currency_field = self._build_contract_currency_expression()
            contract_value = self._build_contract_value_expression()

            client_expression = client_field.label("client")
            currency_expression = currency_field.label("currency")
            total_value_expression = func.coalesce(func.sum(contract_value), 0.0).label("total_value")
            contracts_count_expression = func.count(col(DocumentTable.id)).label("contracts_count")

            statement = select(
                client_expression,
                currency_expression,
                total_value_expression,
                contracts_count_expression,
            )
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
            if chatbot_ready_only:
                statement = self._apply_chatbot_ready_contract_filters(statement)
            statement = statement.group_by(client_field, currency_field)
            statement = self._apply_client_ranking_sorting(
                statement=statement,
                query=query,
                client_expression=client_expression,
                currency_expression=currency_expression,
                total_value_expression=total_value_expression,
                contracts_count_expression=contracts_count_expression,
            )

            if limit is not None:
                statement = statement.limit(limit)

            result = await self.session.exec(statement=statement)
            rows = result.all()

            serialized_rows: list[dict[str, object]] = []
            for row in rows:
                mapping = row._mapping if hasattr(row, "_mapping") else None
                serialized_rows.append(
                    {
                        "client": mapping["client"] if mapping else row[0],
                        "currency": mapping["currency"] if mapping else row[1],
                        "total_value": float((mapping["total_value"] if mapping else row[2]) or 0.0),
                        "contracts_count": int((mapping["contracts_count"] if mapping else row[3]) or 0),
                    }
                )

            return serialized_rows
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def count_contracts(self, organization_id: int, query: ContractQueryDTO, chatbot_ready_only: bool = False) -> int:
        """Cuenta contratos aplicando filtros estructurados."""
        try:
            statement = select(func.count()).select_from(DocumentTable)
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
            if chatbot_ready_only:
                statement = self._apply_chatbot_ready_contract_filters(statement)
            result = await self.session.exec(statement=statement)
            count = result.one()
            return int(count or 0)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def sync_contract_states(self, organization_id: int) -> int:
        """Sincroniza estados documentales persistidos según reglas de notificación."""
        try:
            result = await self.session.exec(
                type_cast(Any, text("select public.sync_document_states(:organization_id)")),
                params={"organization_id": organization_id},
            )
            return self._read_scalar_result(result.one())
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    # ──────────────────────────────────────
    #  DocumentCommandRepository
    # ──────────────────────────────────────

    async def upsert_company_contract(self, entity: CompanyContractTable) -> CompanyContractTable:
        """Creates or updates company-specific data for a document."""
        try:
            existing = await self.get_company_contract_by_document_id(document_id=entity.document_id)
            if existing is None:
                self.session.add(entity)
                await self.session.commit()
                await self.session.refresh(entity)
                return entity

            existing.ruc = entity.ruc
            existing.client = entity.client
            existing.updated_at = entity.updated_at
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DocumentDatabaseError() from e

    async def upsert_labor_contract(self, entity: LaborContractTable) -> LaborContractTable:
        """Creates or updates labor-specific data for a document."""
        try:
            existing = await self.get_labor_contract_by_document_id(document_id=entity.document_id)
            if existing is None:
                self.session.add(entity)
                await self.session.commit()
                await self.session.refresh(entity)
                return entity

            existing.worker_name = entity.worker_name
            existing.worker_document_number = entity.worker_document_number
            existing.position = entity.position
            existing.salary_value = entity.salary_value
            existing.salary_currency = entity.salary_currency
            existing.salary_periodicity = entity.salary_periodicity
            existing.contract_modality = entity.contract_modality
            existing.updated_at = entity.updated_at
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DocumentDatabaseError() from e

    async def replace_document_services(self, doc_id: int, service_items: Sequence[CompanyContractServiceTable]) -> Sequence[CompanyContractServiceTable]:
        """Reemplaza el conjunto de servicios asociados a un documento."""
        try:
            company_contract = await self.get_company_contract_by_document_id(document_id=doc_id)
            if company_contract is None or company_contract.id is None:
                return []

            await self.session.exec(
                delete(CompanyContractServiceTable).where(col(CompanyContractServiceTable.company_contract_id) == company_contract.id)
            )

            if service_items:
                self.session.add_all(service_items)

            await self.session.commit()
            query = (
                select(CompanyContractServiceTable)
                .where(col(CompanyContractServiceTable.company_contract_id) == company_contract.id)
                .order_by(col(CompanyContractServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            return result.all()

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseError() from e
