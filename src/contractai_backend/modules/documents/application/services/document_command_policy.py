"""Application policy helpers for document commands."""

from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .....core.application.validation import format_pydantic_validation_error
from ...api.schemas import DocumentServiceItemRequest
from ...domain import CompanyContractServiceTable, DocumentTable
from ...domain.exceptions import DocumentValidationError
from ....catalog.application.repositories import ServiceRepository


class DocumentCommandPolicy:
    """Holds command-side validation that needs application context."""

    def __init__(self, service_repo: ServiceRepository):
        """Stores the repository used by policy checks."""
        self.service_repo = service_repo

    def validate_document(self, payload: dict[str, Any]) -> DocumentTable:
        """Builds and validates a document entity from raw data."""
        try:
            return DocumentTable.model_validate(obj=payload)
        except PydanticValidationError as exc:
            message = format_pydantic_validation_error(exc=exc, default_field="documento")
            raise DocumentValidationError(message) from exc

    @staticmethod
    def build_document_service_entities(
        company_contract_id: int,
        service_items: Sequence[DocumentServiceItemRequest],
    ) -> list[CompanyContractServiceTable]:
        """Maps request items into document-service entities."""
        return [
            CompanyContractServiceTable(
                company_contract_id=company_contract_id,
                service_id=item.service_id,
                description=item.description,
                value=item.value,
                currency=item.currency,
                start_date=item.start_date,
                end_date=item.end_date,
            )
            for item in service_items
        ]

    @staticmethod
    def normalize_form_data(
        base_form_data: dict[str, Any],
        service_items: Sequence[DocumentServiceItemRequest],
    ) -> dict[str, Any]:
        """Normalizes form data derived from service items."""
        payload = dict(base_form_data)
        payload.pop("licenses", None)

        if service_items:
            payload["value"] = sum(item.value for item in service_items)
            payload["currency"] = service_items[0].currency.value

        return payload

    async def validate_requested_services(
        self,
        organization_id: int,
        service_items: Sequence[DocumentServiceItemRequest],
    ) -> None:
        """Checks that requested service ids exist for the org."""
        if not service_items:
            return

        requested_ids = [item.service_id for item in service_items]
        existing_services = await self.service_repo.get_services_by_ids(organization_id=organization_id, service_ids=requested_ids)
        existing_ids = {service.id for service in existing_services if service.id is not None}
        missing_ids = sorted(set(requested_ids) - existing_ids)

        if missing_ids:
            raise DocumentValidationError(message=f"Los servicios con IDs {missing_ids} no existen o no pertenecen a la organización actual.")
