"""PostgreSQL implementation of document query and command repositories."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from difflib import SequenceMatcher
import re
import unicodedata

from loguru import logger
from sqlalchemy import Float, asc, case, cast, desc, func, or_, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ..application.dto import ContractQueryDTO
from ..application.repositories import DocumentCommandRepository, DocumentQueryRepository
from ..domain import DocumentServiceTable, DocumentTable
from ..domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError
from ....shared.infrastructure.sqlmodel_utils import RelationalHelpersMixin


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
        return cast(DocumentTable.form_data["value"].astext, Float)

    @staticmethod
    def _build_contract_currency_expression():
        return func.upper(DocumentTable.form_data["currency"].astext)

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
            "client": col(DocumentTable.client),
            "name": col(DocumentTable.name),
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

    def _apply_contract_filters(
        self,
        statement,
        organization_id: int,
        filters: ContractQueryDTO,
    ):
        """Aplica los filtros de búsqueda de contratos a la consulta base."""
        statement = statement.where(DocumentTable.organization_id == organization_id)

        text_filters = (
            (filters.client, DocumentTable.client),
            (filters.contract_name, DocumentTable.name),
        )
        for raw_value, field in text_filters:
            normalized_value = self._normalize_text_filter(raw_value)
            if normalized_value:
                statement = statement.where(col(field).ilike(f"%{normalized_value}%"))

        contract_value = self._build_contract_value_expression()
        if filters.min_value is not None:
            statement = statement.where(contract_value >= filters.min_value)
        if filters.max_value is not None:
            statement = statement.where(contract_value <= filters.max_value)

        if filters.currency:
            statement = statement.where(func.upper(DocumentTable.form_data["currency"].astext) == filters.currency)

        exact_filters = (
            (filters.state, col(DocumentTable.state)),
            (filters.document_type, col(DocumentTable.type)),
        )
        for value, field in exact_filters:
            if value is not None:
                statement = statement.where(field == value)

        statement = self._apply_period_filters(statement=statement, filters=filters)
        return self._apply_current_activity_filter(statement=statement, filters=filters)

    # ──────────────────────────────────────
    #  DocumentQueryRepository
    # ──────────────────────────────────────

    async def get_document_services(self, doc_id: int) -> Sequence[DocumentServiceTable]:
        """Obtiene los servicios asociados a un documento."""
        try:
            query = select(DocumentServiceTable).where(col(DocumentServiceTable.document_id) == doc_id).order_by(col(DocumentServiceTable.id))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contract_access_candidates(
        self, organization_id: int, query: str, limit: int = 10
    ) -> Sequence[dict[str, str | int | float | None]]:
        """Searches real contracts by counterparty name for access decisions."""
        normalized_query = self._normalize_lookup_text(query)
        if not normalized_query:
            return []

        try:
            statement = (
                select(
                    col(DocumentTable.id).label("document_id"),
                    col(DocumentTable.name).label("name"),
                    col(DocumentTable.client).label("client"),
                    col(DocumentTable.type).label("document_type"),
                    col(DocumentTable.file_name).label("file_name"),
                )
                .where(DocumentTable.organization_id == organization_id)
                .where(col(DocumentTable.client).is_not(None))
                .where(col(DocumentTable.type).is_not(None))
            )

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

    async def get_document_services_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, Sequence[DocumentServiceTable]]:
        """Obtiene los servicios asociados a múltiples documentos en una sola consulta."""
        if not document_ids:
            return {}

        try:
            query = (
                select(DocumentServiceTable)
                .where(col(DocumentServiceTable.document_id).in_(document_ids))
                .order_by(col(DocumentServiceTable.document_id), col(DocumentServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            grouped_services: defaultdict[int, list[DocumentServiceTable]] = defaultdict(list)
            for service_item in result.all():
                grouped_services[service_item.document_id].append(service_item)
            return dict(grouped_services)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contracts(self, organization_id: int, query: ContractQueryDTO, limit: int | None = None) -> Sequence[DocumentTable]:
        """Obtiene contratos aplicando filtros estructurados."""
        try:
            statement = select(DocumentTable)
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
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
    ) -> Sequence[dict[str, object]]:
        """Construye un ranking agregado por cliente y moneda."""
        try:
            client_field = col(DocumentTable.client)
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

    async def count_contracts(self, organization_id: int, query: ContractQueryDTO) -> int:
        """Cuenta contratos aplicando filtros estructurados."""
        try:
            statement = select(func.count()).select_from(DocumentTable)
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
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
                text("select public.sync_document_states(:organization_id)"),
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

    async def replace_document_services(self, doc_id: int, service_items: Sequence[DocumentServiceTable]) -> Sequence[DocumentServiceTable]:
        """Reemplaza el conjunto de servicios asociados a un documento."""
        try:
            await self.session.exec(delete(DocumentServiceTable).where(col(DocumentServiceTable.document_id) == doc_id))

            if service_items:
                self.session.add_all(service_items)

            await self.session.commit()
            query = select(DocumentServiceTable).where(col(DocumentServiceTable.document_id) == doc_id).order_by(col(DocumentServiceTable.id))
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
